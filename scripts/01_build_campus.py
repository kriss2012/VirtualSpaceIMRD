"""
01_build_campus.py
==================
Procedural 3D model of the RCPET IMRD campus (Blender 5.x, bpy).

Phase 2 refactor:
* Idempotent: only objects/collections owned by this builder (custom property
  ``imrd_owner == "campus_builder"``) are removed and rebuilt. Unrelated scene
  content, other modules' collections (Player_Student, NPCs_and_Interactives)
  and the factory state are never touched.
* Geometry generation is split into functions; configuration lives in
  ``game_config.py`` (all dimensions are approximate - see that module).
* Walls get REAL openings (exact Boolean difference, then verified) with
  frames, inset glass and hinged doors (origin == hinge).
* Staircase is derived from configured floor elevations and the first-floor
  slab has a matching opening.

Usage (headless):
    blender --background --python scripts/01_build_campus.py -- [--render] [--no-save]
"""

import bpy
import bmesh
import math
import shutil
import sys
import time
from pathlib import Path
from mathutils import Vector, Euler, Matrix

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import game_config as cfg  # noqa: E402
import materials_pbr       # noqa: E402

PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
BLEND_FILE = OUTPUT_DIR / "imrd_campus.blend"

OWNER_KEY = cfg.OWNER_KEY
OWNER_VALUE = cfg.OWNER_VALUE


class BuildError(RuntimeError):
    """Raised when a geometry step fails (message names the failing object)."""


# ----------------------------------------------------------------------
# Scene / collection management (idempotent)
# ----------------------------------------------------------------------
def _scene_collection_names(scene):
    return {c.name for c in scene.collection.children_recursive}


def ensure_collections(scene):
    """Create (or reuse) every owned collection and make sure it is in the scene."""
    cols = {}
    linked = _scene_collection_names(scene)
    for key, name in cfg.COLLECTIONS.items():
        col = bpy.data.collections.get(name)
        if col is None:
            col = bpy.data.collections.new(name)
        if name not in linked:
            scene.collection.children.link(col)
        col[OWNER_KEY] = OWNER_VALUE
        cols[key] = col
    return cols


def is_owned(idb):
    return idb.get(OWNER_KEY) == OWNER_VALUE


def remove_object(obj):
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0:
        for coll in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras):
            if data.name in coll and coll[data.name] is data:
                coll.remove(data)
                break


def clear_owned(cols):
    """Remove only builder-owned objects inside the builder-owned collections."""
    removed = 0
    for col in cols.values():
        for obj in list(col.objects):
            if is_owned(obj):
                remove_object(obj)
                removed += 1
    # Remove stray owned objects that were moved out of our collections
    for obj in list(bpy.data.objects):
        if is_owned(obj):
            remove_object(obj)
            removed += 1
    return removed


def remove_default_startup_objects():
    """Delete Blender's untouched default Cube/Camera/Light of an unsaved session."""
    if bpy.data.filepath:
        return
    for name in ("Cube", "Camera", "Light"):
        obj = bpy.data.objects.get(name)
        if obj is not None and not is_owned(obj):
            remove_object(obj)


# ----------------------------------------------------------------------
# Materials (centralized PBR library from materials_pbr.py)
# ----------------------------------------------------------------------
def create_material(name, base_color, roughness=0.6, metallic=0.0,
                    emission_color=(0, 0, 0, 1), emission_strength=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    if mat.node_tree is None:
        mat.use_nodes = True   # legacy fallback; Blender 5.x creates a node tree by default
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*base_color[:3], 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission_strength > 0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission_color[:3], 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    mat.diffuse_color = (*base_color[:3], 1.0)   # viewport / Workbench colour
    return mat


def make_materials():
    return materials_pbr.build_full_pbr_palette()


# ----------------------------------------------------------------------
# Mesh primitives (bmesh, no operators => no context dependence)
# ----------------------------------------------------------------------
def box_into(bm, center, size, origin=(0, 0, 0), rot=None):
    """Append an axis box (optionally rotated about its centre) in object space."""
    verts = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    for v in verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if rot is not None:
        bmesh.ops.rotate(bm, verts=verts, cent=(0, 0, 0), matrix=rot)
    off = Vector(center) - Vector(origin)
    for v in verts:
        v.co += off
    return verts


def cylinder_into(bm, center, radius, depth, origin=(0, 0, 0), rot=None, segments=24):
    verts = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                                  radius1=radius, radius2=radius, depth=depth)["verts"]
    if rot is not None:
        bmesh.ops.rotate(bm, verts=verts, cent=(0, 0, 0), matrix=rot)
    off = Vector(center) - Vector(origin)
    for v in verts:
        v.co += off
    return verts


def beam_into(bm, p0, p1, thick, origin=(0, 0, 0)):
    """Square-section beam from p0 to p1 (world coords)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    rot = d.normalized().to_track_quat('Z', 'Y').to_matrix()
    box_into(bm, (p0 + p1) / 2, (thick, thick, d.length), origin=origin, rot=rot)


class Builder:
    """Holds scene, collections, materials and the object factory."""

    def __init__(self, scene, cols, mats):
        self.scene = scene
        self.cols = cols
        self.mats = mats
        self.name_clashes = []
        self.stats = {"walls": {}, "doors": [], "cut_openings": 0}

    # -- factory ------------------------------------------------------
    def _finish(self, name, bm, col, mat, origin=(0, 0, 0), props=None):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(name, me)
        if obj.name != name:
            self.name_clashes.append((name, obj.name))
        obj.location = Vector(origin)
        if mat is not None:
            me.materials.append(mat)
        obj[OWNER_KEY] = OWNER_VALUE
        for k, v in (props or {}).items():
            obj[k] = v
        col.objects.link(obj)
        return obj

    def box(self, col, name, center, size, mat=None, origin=None, rot=None, props=None):
        bm = bmesh.new()
        o = center if origin is None else origin
        box_into(bm, center, size, origin=o, rot=rot)
        return self._finish(name, bm, col, mat, origin=o, props=props)

    def cyl(self, col, name, center, radius, depth, mat=None, rot=None, segments=24):
        bm = bmesh.new()
        cylinder_into(bm, center, radius, depth, origin=center, rot=rot, segments=segments)
        return self._finish(name, bm, col, mat, origin=center)

    def multi(self, col, name, boxes, mat=None, origin=(0, 0, 0)):
        """Several boxes (center, size) merged into one object."""
        bm = bmesh.new()
        for center, size in boxes:
            box_into(bm, center, size, origin=origin)
        return self._finish(name, bm, col, mat, origin=origin)


# ----------------------------------------------------------------------
# Wall-axis helpers
# ----------------------------------------------------------------------
def P(axis, fixed, along, off, z):
    """World point for wall running along `axis` at `fixed`."""
    return (along, fixed + off, z) if axis == "X" else (fixed + off, along, z)


def S(axis, s_along, s_across, s_z):
    return (s_along, s_across, s_z) if axis == "X" else (s_across, s_along, s_z)


def mesh_health(obj):
    """Return (non_manifold_edge_count, signed_volume, face_count)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    vol = 0.0
    for f in bm.faces:
        v = [l.vert.co for l in f.loops]
        for i in range(1, len(v) - 1):
            vol += v[0].dot(v[i].cross(v[i + 1])) / 6.0
    n = len(bm.faces)
    bm.free()
    return bad, vol, n


def cut_openings(b, wall_obj, wall, openings):
    """Boolean-subtract all openings from wall_obj, replacing its mesh by the exact result."""
    axis, fixed, thick = wall["axis"], wall["fixed"], wall["thick"]
    wz0, wz1 = wall["z"]
    bm = bmesh.new()
    for op in openings:
        z0 = op["z0"] - (0.2 if op["z0"] <= wz0 + 1e-6 else 0.0)
        z1 = op["z1"]
        box_into(bm, P(axis, fixed, op["along"], 0, (z0 + z1) / 2),
                 S(axis, op["width"], thick + 0.4, z1 - z0))
    cutter = b._finish(f"_cutter_{wall_obj.name}", bm, b.cols["architecture"], None)

    mod = wall_obj.modifiers.new("OpeningCut", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = wall_obj.evaluated_get(dg)
    new_mesh = bpy.data.meshes.new_from_object(ev)
    wall_obj.modifiers.remove(mod)
    old = wall_obj.data
    new_mesh.name = wall_obj.name
    wall_obj.data = new_mesh
    bpy.data.meshes.remove(old)
    new_mesh.materials.clear()
    new_mesh.materials.append(b.mats["wall_ext"] if wall["ext"] else b.mats["wall_int"])
    remove_object(cutter)

    # merge coplanar triangles produced by the Boolean
    bm = bmesh.new()
    bm.from_mesh(new_mesh)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(new_mesh)
    bm.free()

    bad, vol, nf = mesh_health(wall_obj)
    b.stats["walls"][wall_obj.name] = {"non_manifold": bad, "volume": round(vol, 3), "faces": nf,
                                       "openings": len(openings)}
    b.stats["cut_openings"] += len(openings)
    if bad or vol <= 0:
        raise BuildError(f"{wall_obj.name}: Boolean result invalid (non-manifold={bad}, volume={vol:.3f})")


# ----------------------------------------------------------------------
# Terrain, roads and plazas (unchanged layout from the blockout)
# ----------------------------------------------------------------------
def build_terrain(b):
    col, m = b.cols["terrain"], b.mats
    b.box(col, "Ground_Grass", (0, 30, -0.1), (220, 180, 0.2), m["grass"])
    b.box(col, "Road_Main", (0, 48, 0.02), (9.0, 56.0, 0.04), m["asphalt"])
    for z in range(22, 74, 5):
        b.box(col, f"Road_Dash_{z}", (0, z, 0.045), (0.25, 2.5, 0.02), m["road_lines"])
    b.box(col, "Road_Branch_Parking", (18, 37, 0.02), (26.0, 7.0, 0.04), m["asphalt"])
    b.box(col, "Parking_Area", (44, 43, 0.025), (34.0, 24.0, 0.04), m["parking"])
    for k in range(9):
        x = 30 + k * 3.4
        b.box(col, f"Parking_Line_A_{k}", (x, 36, 0.05), (0.15, 6.0, 0.02), m["park_lines"])
        b.box(col, f"Parking_Line_B_{k}", (x, 50, 0.05), (0.15, 6.0, 0.02), m["park_lines"])
    b.box(col, "Plaza_Front", (0, 15, 0.03), (48.0, 10.0, 0.05), m["paving"])
    b.box(col, "Walkway_Garden_A", (-22.5, 34, 0.03), (3.0, 30.0, 0.05), m["paving"])
    b.box(col, "Walkway_Garden_B", (-31, 48.5, 0.03), (16.0, 3.0, 0.05), m["paving"])
    b.cyl(col, "Garden_Circle_Plaza", (-40, 48.5, 0.035), 6.0, 0.04, m["paving"], segments=48)
    b.cyl(col, "Garden_Flowerbed", (-40, 48.5, 0.08), 2.5, 0.08, m["leaves"], segments=32)
    b.box(col, "Walkway_Parking", (22.5, 27, 0.03), (3.0, 16.0, 0.05), m["paving"])


# ----------------------------------------------------------------------
# Building shell: plinth, slabs, roof, canopy, balcony
# ----------------------------------------------------------------------
def build_shell(b):
    col, m = b.cols["architecture"], b.mats
    px, py = cfg.PLINTH_HALF
    b.box(col, "Bld_Plinth", (0, 0, cfg.PLINTH_TOP_Z / 2), (2 * px, 2 * py, cfg.PLINTH_TOP_Z), m["paving"])
    b.box(col, "Bld_Steps_1", (0, 9.4, 0.1), (14.0, 2.0, 0.2), m["paving"])
    b.box(col, "Bld_Steps_2", (0, 10.2, 0.05), (16.0, 1.8, 0.1), m["paving"])

    # Ground floor finish (inside the exterior walls)
    b.box(col, "Bld_Floor_G", (0, 0, cfg.PLINTH_TOP_Z + cfg.SLAB_G_THICK / 2),
          (2 * cfg.BLD_IN_X, 2 * cfg.BLD_IN_Y, cfg.SLAB_G_THICK), m["floor_tile"])

    # First-floor slab built in 4 pieces around the stair opening (clean, no Boolean needed)
    sx, sy = cfg.SLAB_1_HALF
    z_c = cfg.FLOOR_1_Z - cfg.SLAB_1_THICK / 2
    t = cfg.SLAB_1_THICK
    ox0, ox1 = cfg.STAIR_OPEN_X
    oy0, oy1 = cfg.STAIR_OPEN_Y
    pieces = {
        "Slab_Floor_1_West": ((-sx, ox0), (-sy, sy)),
        "Slab_Floor_1_East": ((ox1, sx), (-sy, sy)),
        "Slab_Floor_1_Front": ((ox0, ox1), (oy1, sy)),
        "Slab_Floor_1_Landing": ((ox0, ox1), (-sy, oy0)),
    }
    for name, ((x0, x1), (y0, y1)) in pieces.items():
        b.box(col, name, ((x0 + x1) / 2, (y0 + y1) / 2, z_c), (x1 - x0, y1 - y0, t), m["paving"])

    # Roof and parapets
    rx, ry = cfg.ROOF_HALF
    b.box(col, "Roof_Main", (0, 0, cfg.ROOF_BOTTOM_Z + cfg.ROOF_THICK / 2), (2 * rx, 2 * ry, cfg.ROOF_THICK), m["paving"])
    pz = cfg.ROOF_TOP_Z + cfg.PARAPET_H / 2
    b.box(col, "Parapet_Front", (0, 8.75, pz), (42.0, 0.3, cfg.PARAPET_H), m["wall_trim"])
    b.box(col, "Parapet_Back", (0, -8.75, pz), (42.0, 0.3, cfg.PARAPET_H), m["wall_trim"])
    b.box(col, "Parapet_Left", (-20.85, 0, pz), (0.3, 17.6, cfg.PARAPET_H), m["wall_trim"])
    b.box(col, "Parapet_Right", (20.85, 0, pz), (0.3, 17.6, cfg.PARAPET_H), m["wall_trim"])
    # Signboard now mounted on the parapet (previously collided with the balcony)
    b.box(col, "Building_Sign_Panel", (0, 8.96, pz), (11.0, 0.12, 0.8), m["wall_trim"])

    # Entrance canopy == first-floor balcony. Starts at the slab edge (no coplanar overlap).
    cy0, cy1 = cfg.SLAB_1_HALF[1], 12.5
    b.box(col, "Canopy_Roof", (0, (cy0 + cy1) / 2, z_c), (13.0, cy1 - cy0, t), m["wall_trim"])
    for side, nm in ((-1, "L"), (1, "R")):
        b.cyl(col, f"Column_Canopy_{nm}", (side * 5.5, 12.0, cfg.G_CEILING_Z / 2), 0.28, cfg.G_CEILING_Z, m["wall_trim"])

    # Balcony guard rail (front + both sides), 1.0 m high
    zb = cfg.FLOOR_1_Z
    bm = bmesh.new()
    runs = [((-6.4, 12.4), (6.4, 12.4)), ((-6.4, cfg.SLAB_1_HALF[1]), (-6.4, 12.4)),
            ((6.4, cfg.SLAB_1_HALF[1]), (6.4, 12.4))]
    for (xa, ya), (xb, yb) in runs:
        beam_into(bm, (xa, ya, zb + 1.0), (xb, yb, zb + 1.0), 0.06)
        beam_into(bm, (xa, ya, zb + 0.5), (xb, yb, zb + 0.5), 0.04)
        n = max(2, int(math.hypot(xb - xa, yb - ya) / 1.2) + 1)
        for i in range(n + 1):
            f = i / n
            x, y = xa + (xb - xa) * f, ya + (yb - ya) * f
            box_into(bm, (x, y, zb + 0.5), (0.06, 0.06, 1.0))
    b._finish("Rail_Balcony", bm, col, m["metal_dark"])


# ----------------------------------------------------------------------
# Walls, openings, frames, glass, doors
# ----------------------------------------------------------------------
def _opening_frame(b, wall, op, col):
    axis, fixed, thick = wall["axis"], wall["fixed"], wall["thick"]
    fw = op["frame_w"]
    depth = thick + cfg.WINDOW_FRAME_PROUD
    c, w, z0, z1 = op["along"], op["width"], op["z0"], op["z1"]
    boxes = []
    for sgn in (-1, 1):   # jambs
        boxes.append((P(axis, fixed, c + sgn * (w / 2 - fw / 2), 0, (z0 + z1) / 2),
                      S(axis, fw, depth, z1 - z0)))
    boxes.append((P(axis, fixed, c, 0, z1 - fw / 2), S(axis, w, depth, fw)))   # head
    if op["kind"] == "WINDOW":
        boxes.append((P(axis, fixed, c, 0, z0 + fw / 2), S(axis, w, depth + 0.06, fw)))  # sill
    mat = b.mats["wall_trim"] if wall["ext"] else b.mats["wood"]
    b.multi(col, f"Frame_{op['name']}", boxes, mat)


def _opening_glass(b, wall, op, col):
    axis, fixed = wall["axis"], wall["fixed"]
    fw = op["frame_w"]
    h = op["z1"] - op["z0"] - 2 * fw
    b.box(col, f"Glass_{op['name']}",
          P(axis, fixed, op["along"], 0, (op["z0"] + op["z1"]) / 2),
          S(axis, op["width"] - 2 * fw, cfg.WINDOW_GLASS_T, h), b.mats["glass"])


def _door_leaf(b, wall, op, hinge_side, swing, leaf_name, extra_props):
    """Create a door leaf whose origin is the hinge point; mesh extends from the hinge."""
    axis, fixed = wall["axis"], wall["fixed"]
    fw = op["frame_w"]
    floor_z = cfg.FLOORS[wall["floor"]]
    lw, lh, lt = op["leaf_w"], op["leaf_h"], op["leaf_t"]
    hinge_inset = fw + lt / 2 + cfg.DOOR_HINGE_GAP
    if hinge_side == "lo":
        hinge_along, dirn = op["along"] - op["width"] / 2 + hinge_inset, +1
    else:
        hinge_along, dirn = op["along"] + op["width"] / 2 - hinge_inset, -1
    base_z = floor_z + cfg.DOOR_BOTTOM_CLEARANCE
    hinge = Vector(P(axis, fixed, hinge_along, 0, base_z))
    dvec = Vector((dirn, 0, 0)) if axis == "X" else Vector((0, dirn, 0))
    nvec = Vector((0, swing, 0)) if axis == "X" else Vector((swing, 0, 0))
    open_sign = 1.0 if (dvec.x * nvec.y - dvec.y * nvec.x) > 0 else -1.0
    open_deg = open_sign * cfg.DOOR_OPEN_DEG
    center = hinge + dvec * (lw / 2) + Vector((0, 0, lh / 2))
    props = {
        "imrd_door_id": op["id"], "imrd_wall": wall["name"], "imrd_hinge": list(hinge),
        "imrd_closed_rot_z_deg": 0.0, "imrd_open_rot_z_deg": open_deg, "imrd_state": "CLOSED",
        "imrd_leaf_size": [lw, lt, lh],
    }
    props.update(extra_props)
    obj = b.box(b.cols["gameplay"], leaf_name, tuple(center), S(axis, lw, lt, lh), b.mats["door"],
                origin=tuple(hinge), props=props)
    b.stats["doors"].append({"name": leaf_name, "id": op["id"], "hinge": [round(v, 3) for v in hinge],
                             "open_deg": open_deg})
    return obj


def build_walls_and_openings(b):
    col = b.cols["architecture"]
    icol = b.cols["interior_arch"]
    by_wall = {}
    for op in cfg.OPENINGS:
        by_wall.setdefault(op["wall"], []).append(op)

    for key, wall in cfg.WALLS.items():
        a0, a1 = wall["a0"], wall["a1"]
        z0, z1 = wall["z"]
        axis, fixed, thick = wall["axis"], wall["fixed"], wall["thick"]
        length, h = a1 - a0, z1 - z0
        mid = (a0 + a1) / 2
        target = col if wall["ext"] else icol
        mat = b.mats["wall_ext"] if wall["ext"] else b.mats["wall_int"]
        obj = b.box(target, wall["name"], P(axis, fixed, mid, 0, z0 + h / 2),
                    S(axis, length, thick, h), mat)
        ops = by_wall.get(key, [])
        if ops:
            cut_openings(b, obj, wall, ops)
        for op in ops:
            _opening_frame(b, wall, op, target)
            if op["kind"] == "WINDOW":
                _opening_glass(b, wall, op, target)
            elif op["kind"] == "DOOR":
                _door_leaf(b, wall, op, op["hinge"], op["swing"], op["door_name"], {})
            elif op["kind"] == "ENTRANCE":
                _door_leaf(b, wall, op, "lo", op["swing"], cfg.ENTRANCE_DOOR_NAME, {})
                _door_leaf(b, wall, op, "hi", op["swing"], cfg.ENTRANCE_DOOR_B_NAME, {})


# ----------------------------------------------------------------------
# Staircase
# ----------------------------------------------------------------------
def build_stairs(b):
    col, m = b.cols["interior_arch"], b.mats
    R, T, W = cfg.STAIR_RISER_H, cfg.STAIR_TREAD_D, cfg.STAIR_W
    fz = cfg.FLOOR_G_Z
    for i in range(1, cfg.STAIR_TREAD_COUNT + 1):
        top = fz + i * R
        y_front = cfg.STAIR_Y_START - (i - 1) * T
        b.box(col, f"Stair_Step_{i:02d}", (cfg.STAIR_X, y_front - T / 2, (fz + top) / 2),
              (W, T, top - fz), m["paving"])

    # Handrails: sloped rail + posts on both sides, ending at the top edge
    slope = R / T
    y_a = cfg.STAIR_Y_START - T / 2
    z_a = fz + R + cfg.STAIR_RAIL_H
    y_b = cfg.STAIR_Y_TOP
    z_b = z_a + (y_a - y_b) * slope
    for side, nm in ((-1, "L"), (1, "R")):
        x = cfg.STAIR_X + side * (W / 2 + 0.025)
        bm = bmesh.new()
        beam_into(bm, (x, y_a, z_a), (x, y_b, z_b), 0.05)
        for i in range(1, cfg.STAIR_TREAD_COUNT + 1, 4):
            ym = cfg.STAIR_Y_START - (i - 1) * T - T / 2
            top = fz + i * R
            box_into(bm, (x, ym, (top + z_a + (y_a - ym) * slope) / 2),
                     (0.04, 0.04, (z_a + (y_a - ym) * slope) - top))
        b._finish(f"Rail_Stair_{nm}", bm, col, m["metal_dark"])

    # Guard on the open slab edge at the stair's lower end (upper floor side)
    ox0, ox1 = cfg.STAIR_OPEN_X
    yg = cfg.STAIR_OPEN_Y[1] - 0.025
    zf = cfg.FLOOR_1_Z
    bm = bmesh.new()
    beam_into(bm, (ox0, yg, zf + 1.0), (ox1, yg, zf + 1.0), 0.05)
    beam_into(bm, (ox0, yg, zf + 0.5), (ox1, yg, zf + 0.5), 0.04)
    for x in (ox0 + 0.025, (ox0 + ox1) / 2, ox1 - 0.025):
        box_into(bm, (x, yg, zf + 0.5), (0.05, 0.05, 1.0))
    b._finish("Rail_Stair_Opening_Front", bm, col, m["metal_dark"])


# ----------------------------------------------------------------------
# Interior furniture (heights now derived from the floor elevations)
# ----------------------------------------------------------------------
def build_furniture(b):
    col, m = b.cols["furniture"], b.mats
    g, f1 = cfg.FLOOR_G_Z, cfg.FLOOR_1_Z
    y_wall = cfg.PARTITION_Y + cfg.INT_WALL_T / 2   # flush with partition face

    b.box(col, "Reception_Counter", (-3.5, 4.0, g + 0.5), (3.0, 1.0, 1.0), m["wood"])
    b.box(col, "Reception_Chair", (-3.5, 3.0, g + 0.4), (0.6, 0.6, 0.8), m["metal_dark"])

    b.box(col, "Class_G_Blackboard", (-14.0, y_wall + 0.04, g + 1.9), (4.5, 0.08, 1.4), m["board"])
    b.box(col, "Teacher_Table_G", (-14.0, 1.6, g + 0.4), (2.2, 0.9, 0.8), m["wood"])
    for row in range(3):
        for ci in range(3):
            x, y = -17.5 + ci * 2.8, 3.2 + row * 1.5
            b.box(col, f"Desk_G_{row}_{ci}", (x, y, g + 0.35), (1.4, 0.6, 0.7), m["wood"])
            b.box(col, f"Bench_G_{row}_{ci}", (x, y + 0.5, g + 0.225), (1.3, 0.35, 0.45), m["metal_dark"])

    b.box(col, "Class_1_Whiteboard", (14.0, y_wall + 0.04, f1 + 1.9), (4.5, 0.08, 1.4), m["wall_ext"])
    b.box(col, "Teacher_Table_1", (14.0, 1.6, f1 + 0.4), (2.2, 0.9, 0.8), m["wood"])
    for row in range(3):
        for ci in range(3):
            x, y = 10.5 + ci * 2.8, 3.2 + row * 1.5
            b.box(col, f"Desk_1_{row}_{ci}", (x, y, f1 + 0.35), (1.4, 0.6, 0.7), m["wood"])
            b.box(col, f"Bench_1_{row}_{ci}", (x, y + 0.5, f1 + 0.225), (1.3, 0.35, 0.45), m["metal_dark"])


# ----------------------------------------------------------------------
# Outdoor props, vehicles, gate, vegetation (layout unchanged)
# ----------------------------------------------------------------------
def build_props(b):
    col, m = b.cols["props"], b.mats
    lamps = [(-5.5, 26), (5.5, 26), (-5.5, 42), (5.5, 42), (-5.5, 58), (5.5, 58),
             (-5.5, 72), (5.5, 72), (-16.0, 15.0), (16.0, 15.0), (-24.0, 48.5)]
    for i, (lx, ly) in enumerate(lamps):
        b.cyl(col, f"Lamp_Pole_{i}", (lx, ly, 2.2), 0.08, 4.4, m["metal_dark"], segments=12)
        b.cyl(col, f"Lamp_Head_{i}", (lx, ly, 4.5), 0.25, 0.25, m["metal_dark"], segments=16)
        b.cyl(col, f"Lamp_Glow_{i}", (lx, ly, 4.35), 0.20, 0.1, m["lamp_glow"], segments=16)

    for idx, bx in enumerate((-14, -7, 7, 14)):
        b.box(col, f"Bench_Plaza_{idx}", (bx, 13, 0.30), (1.8, 0.6, 0.5), m["wood"])
        b.box(col, f"Bench_Plaza_Back_{idx}", (bx, 12.75, 0.80), (1.8, 0.1, 0.5), m["wood"])
    for k in range(4):
        ang = k * (math.pi / 2)
        b.box(col, f"Garden_Bench_{k}", (-40 + math.cos(ang) * 4.2, 48.5 + math.sin(ang) * 4.2, 0.26),
              (1.6, 0.5, 0.4), m["wood"])

    colors = [(0.85, 0.12, 0.12), (0.12, 0.35, 0.85), (0.92, 0.92, 0.92),
              (0.15, 0.15, 0.15), (0.88, 0.75, 0.10), (0.25, 0.65, 0.30)]
    wheel_rot = Matrix.Rotation(math.pi / 2, 3, 'Y')   # wheel axis along X
    for idx in range(6):
        cx, cy = 32.0 + idx * 3.4, 36.0
        cm = materials_pbr.create_car_paint_material(f"Mat_Car_{idx}", colors[idx])
        b.box(col, f"Car_{idx}_Body", (cx, cy, 0.6), (1.8, 4.0, 0.65), cm)
        b.box(col, f"Car_{idx}_Cabin", (cx, cy - 0.2, 1.2), (1.6, 2.2, 0.55), m["glass"])
        k = 0
        for wx in (-0.95, 0.95):
            for wy in (cy - 1.2, cy + 1.2):
                b.cyl(col, f"Car_{idx}_Wheel_{k}", (cx + wx, wy, 0.32), 0.32, 0.2, m["metal_dark"],
                      rot=wheel_rot, segments=20)
                k += 1


def build_gate(b):
    col, m = b.cols["gate"], b.mats
    b.box(col, "Gate_Pillar_L", (-5.5, 75.0, 2.8), (1.2, 1.2, 5.6), m["wall_trim"])
    b.box(col, "Gate_Pillar_R", (5.5, 75.0, 2.8), (1.2, 1.2, 5.6), m["wall_trim"])
    b.box(col, "Gate_Arch_Beam", (0, 75.0, 5.6), (12.2, 1.4, 0.8), m["wall_trim"])
    b.box(col, "Gate_Signboard", (0, 75.0, 6.3), (10.0, 0.2, 0.9), m["wall_ext"])
    b.box(col, "Security_Cabin", (7.8, 73.5, 1.6), (2.8, 2.8, 3.2), m["wall_ext"])
    b.box(col, "Security_Cabin_Roof", (7.8, 73.5, 3.3), (3.2, 3.2, 0.3), m["wall_trim"])
    b.box(col, "Security_Cabin_Window", (6.4, 73.5, 1.6), (0.1, 1.6, 1.2), m["glass"])
    b.box(col, "Boundary_Wall_L", (-25.0, 75.0, 1.1), (38.0, 0.4, 2.2), m["wall_ext"])
    b.box(col, "Boundary_Wall_R", (25.0, 75.0, 1.1), (38.0, 0.4, 2.2), m["wall_ext"])


def build_vegetation(b):
    col, m = b.cols["vegetation"], b.mats
    pos = [(-8.5, 24), (-8.5, 38), (-8.5, 52), (-8.5, 66), (8.5, 24), (8.5, 52), (8.5, 66),
           (-32, 38), (-48, 38), (-32, 58), (-48, 58), (-40, 62), (-54, 48), (-28, 48),
           (-15, -12), (0, -12), (15, -12), (60, 36), (60, 48), (60, 60)]
    for idx, (tx, ty) in enumerate(pos):
        h = 5.0 + (idx % 3) * 0.8
        th, cr = h * 0.45, h * 0.45
        n = f"Tree_{idx}"
        b.cyl(col, f"{n}_Trunk", (tx, ty, th / 2), 0.25, th, m["trunk"], segments=12)
        b.cyl(col, f"{n}_Crown1", (tx, ty, th + cr * 0.6), cr, cr * 1.2, m["leaves"], segments=16)
        b.cyl(col, f"{n}_Crown2", (tx, ty, th + cr * 1.3), cr * 0.75, cr, m["leaves"], segments=16)


# ----------------------------------------------------------------------
# Lights, Sky Atmosphere and Reusable Cameras
# ----------------------------------------------------------------------
def setup_world_sky(scene):
    """Sets up physically plausible Nishita sky texture and EEVEE Next settings."""
    world = scene.world or bpy.data.worlds.new("IMRD_SkyWorld")
    scene.world = world
    if world.node_tree is None:
        world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.location = (-300, 0)
    sky.sun_elevation = math.radians(38.0)  # ~38 degrees above horizon
    sky.sun_rotation = math.radians(135.0)  # coming from SE
    sky.turbidity = 2.4                     # clear atmosphere
    sky.ground_albedo = 0.25

    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (0, 0)
    bg.inputs["Strength"].default_value = 1.0

    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (200, 0)

    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # EEVEE Next raytracing & illumination
    eevee = scene.eevee
    if hasattr(eevee, "use_raytracing"):
        eevee.use_raytracing = True
        if hasattr(eevee, "ray_tracing_options"):
            eevee.ray_tracing_options.screen_trace_quality = 0.50
            eevee.ray_tracing_options.trace_max_roughness = 0.65
    if hasattr(eevee, "fast_gi_method"):
        eevee.fast_gi_method = "GLOBAL_ILLUMINATION"
    if hasattr(eevee, "use_shadows"):
        eevee.use_shadows = True

    # AgX Color Management
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0


def build_lighting_and_cameras(b):
    setup_world_sky(b.scene)
    col = b.cols["lighting"]

    # Primary sun matching Nishita sky elevation (38°) & rotation (135°)
    sun_data = bpy.data.lights.get("Sun_Daylight") or bpy.data.lights.new(name="Sun_Daylight", type='SUN')
    sun_data.energy = 4.0
    sun_data.color = (1.0, 0.98, 0.93)
    if hasattr(sun_data, "angle"):
        sun_data.angle = math.radians(0.54)   # realistic solar angular diameter for soft shadows
    sun_obj = bpy.data.objects.new("Sun_Daylight", sun_data)
    sun_obj.location = (20, -20, 40)
    sun_obj.rotation_euler = Euler((math.radians(52), math.radians(15), math.radians(135)), 'XYZ')
    sun_obj[OWNER_KEY] = OWNER_VALUE
    col.objects.link(sun_obj)

    # Soft ambient fill
    fill_data = bpy.data.lights.get("Sky_Fill") or bpy.data.lights.new(name="Sky_Fill", type='SUN')
    fill_data.energy = 1.2
    fill_data.color = (0.75, 0.88, 1.0)
    fill_obj = bpy.data.objects.new("Sky_Fill", fill_data)
    fill_obj.location = (-20, 20, 35)
    fill_obj.rotation_euler = Euler((math.radians(-50), math.radians(-30), math.radians(-120)), 'XYZ')
    fill_obj[OWNER_KEY] = OWNER_VALUE
    col.objects.link(fill_obj)

    cams = [
        (cfg.CAMERA_OVERVIEW, 35, 400, (65, 105, 55), (64, 0, 145)),
        (cfg.CAMERA_ENTRANCE, 28, 300, (0, 72, 2.2), (85, 0, 180)),
        ("Cam_Facade", 26, 300, (-18.0, 25.0, 2.2), (82, 0, -145)),
        ("Cam_Classroom", 22, 100, (-10.5, 6.8, 1.8), (75, 0, 30)),
        ("Cam_Staircase", 24, 100, (1.8, 6.2, 1.6), (72, 0, -25)),
        ("Cam_Courtyard", 28, 200, (-32.0, 40.0, 1.8), (82, 0, -140)),
    ]
    for name, lens, clip, loc, rot in cams:
        cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
        cd.lens, cd.clip_end = lens, clip
        obj = bpy.data.objects.new(name, cd)
        obj.location = loc
        obj.rotation_euler = Euler([math.radians(a) for a in rot], 'XYZ')
        obj[OWNER_KEY] = OWNER_VALUE
        col.objects.link(obj)

    if b.scene.camera is None or b.scene.camera.name not in bpy.data.objects:
        b.scene.camera = bpy.data.objects[cfg.CAMERA_OVERVIEW]


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------
def build_campus(scene=None, log=print):
    """Build/rebuild the campus. Safe to call repeatedly. Returns a stats dict."""
    scene = scene or bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0 / cfg.UNITS_PER_METER
    remove_default_startup_objects()
    cols = ensure_collections(scene)
    removed = clear_owned(cols)
    mats = make_materials()
    b = Builder(scene, cols, mats)
    steps = [build_terrain, build_shell, build_walls_and_openings, build_stairs,
             build_furniture, build_props, build_gate, build_vegetation, build_lighting_and_cameras]
    for step in steps:
        try:
            step(b)
        except BuildError:
            raise
        except Exception as exc:
            raise BuildError(f"{step.__name__} failed: {exc!r}") from exc
    if b.name_clashes:
        raise BuildError(f"Object name clashes (foreign objects use our names): {b.name_clashes[:5]}")
    b.stats["removed_previous"] = removed
    b.stats["object_count"] = sum(1 for o in bpy.data.objects if is_owned(o))
    log(f"[IMRD Builder] built {b.stats['object_count']} objects "
        f"({b.stats['cut_openings']} wall openings, {len(b.stats['doors'])} door leaves; "
        f"replaced {removed} previous)")
    return b.stats


# ----------------------------------------------------------------------
# Save / preview helpers (only used from the command line entry point)
# ----------------------------------------------------------------------
def save_project(path=BLEND_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        bdir = path.parent / "backups"
        bdir.mkdir(exist_ok=True)
        dst = bdir / f"{path.stem}_{time.strftime('%Y%m%d_%H%M%S')}.blend"
        shutil.copy2(path, dst)
        print(f"[IMRD Builder] backed up previous blend to {dst}")
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print(f"[IMRD Builder] saved {path}")


def _obj_min_z(obj):
    return min((obj.matrix_world @ Vector(c)).z for c in obj.bound_box)


def render_geometry_previews(out_dir=OUTPUT_DIR, res=(1280, 720)):
    """Low-cost Workbench renders: overview, facade and ground/upper plan cut-aways."""
    scene = bpy.context.scene
    r = scene.render
    saved = (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath,
             scene.camera, scene.display.shading.color_type, scene.display.shading.light)
    r.engine = 'BLENDER_WORKBENCH'
    r.resolution_x, r.resolution_y, r.resolution_percentage = res[0], res[1], 100
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.light = 'STUDIO'
    tmp = []

    def shoot(name, cam):
        scene.camera = cam
        r.filepath = str(Path(out_dir) / name)
        bpy.ops.render.render(write_still=True)
        print(f"[IMRD Builder] preview rendered: {r.filepath}")

    def temp_cam(name, loc, rot, ortho=None, lens=35):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_end = 500
        if ortho:
            cd.type, cd.ortho_scale = 'ORTHO', ortho
        o = bpy.data.objects.new(name, cd)
        o.location = loc
        o.rotation_euler = Euler([math.radians(a) for a in rot], 'XYZ')
        scene.collection.objects.link(o)
        tmp.append(o)
        return o

    try:
        shoot("geometry_preview_overview.png", bpy.data.objects[cfg.CAMERA_OVERVIEW])
        shoot("geometry_preview_facade.png", temp_cam("_tmp_facade", (-22, 34, 6), (84, 0, -145), lens=24))
        plan = temp_cam("_tmp_plan", (0, 0, 40), (0, 0, 0), ortho=46)
        for thr, fname in ((cfg.G_CEILING_Z - 0.01, "geometry_preview_plan_ground.png"),
                           (cfg.ROOF_BOTTOM_Z - 0.01, "geometry_preview_plan_upper.png")):
            hidden = []
            for o in bpy.data.objects:
                if o.type == 'MESH' and not o.name.startswith("_tmp") and _obj_min_z(o) >= thr and not o.hide_render:
                    o.hide_render = True
                    hidden.append(o)
            shoot(fname, plan)
            for o in hidden:
                o.hide_render = False
    finally:
        for o in tmp:
            cam = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.cameras.remove(cam)
        (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath,
         scene.camera, scene.display.shading.color_type, scene.display.shading.light) = saved


def render_pbr_showcase(out_dir=OUTPUT_DIR / "renders", res=(1280, 720)):
    """Renders realistic PBR cinematic images using EEVEE Next and Nishita sky."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    r = scene.render

    saved_engine = r.engine
    saved_res_x = r.resolution_x
    saved_res_y = r.resolution_y
    saved_res_pct = r.resolution_percentage
    saved_filepath = r.filepath
    saved_cam = scene.camera

    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = res[0], res[1], 100
    if hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 32

    targets = [
        ("overview_pbr.png", cfg.CAMERA_OVERVIEW),
        ("entrance_pbr.png", cfg.CAMERA_ENTRANCE),
        ("facade_pbr.png", "Cam_Facade"),
        ("classroom_pbr.png", "Cam_Classroom"),
        ("staircase_pbr.png", "Cam_Staircase"),
        ("courtyard_pbr.png", "Cam_Courtyard"),
    ]

    for fname, cname in targets:
        cam_obj = bpy.data.objects.get(cname)
        if cam_obj:
            scene.camera = cam_obj
            target_path = out_dir / fname
            r.filepath = str(target_path)
            try:
                bpy.ops.render.render(write_still=True)
                print(f"[IMRD Builder] PBR showcase rendered: {target_path}")
            except Exception as e:
                print(f"[IMRD Builder] Warning rendering {fname}: {e}")

    # Synchronize legacy root render targets so README and test suites locate them
    for src_name, dst_name in [("overview_pbr.png", "campus_overview.png"),
                               ("entrance_pbr.png", "campus_entrance.png")]:
        src_f = out_dir / src_name
        dst_f = OUTPUT_DIR / dst_name
        if src_f.exists():
            shutil.copy2(src_f, dst_f)
            print(f"[IMRD Builder] Synchronized root render: {dst_f}")

    r.engine = saved_engine
    r.resolution_x = saved_res_x
    r.resolution_y = saved_res_y
    r.resolution_percentage = saved_res_pct
    r.filepath = saved_filepath
    scene.camera = saved_cam


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    try:
        build_campus()
    except BuildError as exc:
        print(f"[IMRD Builder] ERROR: {exc}")
        sys.exit(2)
    if "--no-save" not in argv:
        save_project()
    if "--render" in argv:
        render_geometry_previews()
        render_pbr_showcase()
    print("[IMRD Builder] Done.")


if __name__ == "__main__":
    _main()
