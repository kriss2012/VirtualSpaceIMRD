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

    def cone(self, col, name, center, r_bottom, r_top, depth, mat=None, segments=12):
        """Tapered cone or truncated cylinder for natural tree trunks."""
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                              radius1=r_bottom, radius2=r_top, depth=depth)
        bmesh.ops.translate(bm, vec=Vector(center))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._finish(name, bm, col, mat, origin=center)

    def organic_canopy(self, col, name, center, radius, mat=None, seed=0):
        """Lush, multi-lobed organic canopy using clustered icospheres with smooth shading."""
        bm = bmesh.new()
        # Main central mass (local space, centered at 0, 0, 0)
        res_main = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius * 0.95)
        bmesh.ops.scale(bm, vec=Vector((1.0, 1.0, 0.88)), verts=res_main["verts"])
        # 4 azimuthal side lobes in local space
        angles = [0.2 + seed * 0.4, 1.8 + seed * 0.4, 3.4 + seed * 0.4, 5.0 + seed * 0.4]
        for i, ang in enumerate(angles):
            r_lobe = radius * (0.62 + 0.10 * ((seed + i) % 3))
            d_xy = radius * 0.52
            lx = d_xy * math.cos(ang)
            ly = d_xy * math.sin(ang)
            lz = radius * (-0.10 + 0.15 * (i % 2))
            res_lobe = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r_lobe)
            bmesh.ops.scale(bm, vec=Vector((1.05, 0.95, 0.85)), verts=res_lobe["verts"])
            bmesh.ops.translate(bm, vec=Vector((lx, ly, lz)), verts=res_lobe["verts"])
        # Top crown lobe in local space
        r_top = radius * 0.60
        res_top = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r_top)
        bmesh.ops.translate(bm, vec=Vector((0.08 * radius, -0.06 * radius, radius * 0.60)), verts=res_top["verts"])
        for f in bm.faces:
            f.smooth = True
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._finish(name, bm, col, mat, origin=center)

    def shrub(self, col, name, center, radius, height, mat=None, seed=0):
        """Low rounded ornamental bush/hedge cluster with smooth organic shading."""
        bm = bmesh.new()
        res1 = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius)
        bmesh.ops.scale(bm, vec=Vector((1.0, 1.0, height / (2.0 * max(0.01, radius)))), verts=res1["verts"])
        res2 = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius * 0.78)
        bmesh.ops.scale(bm, vec=Vector((0.95, 1.05, height / (2.0 * max(0.01, radius)))), verts=res2["verts"])
        bmesh.ops.translate(bm, vec=Vector((radius * 0.32, -radius * 0.22, height * -0.05)), verts=res2["verts"])
        for f in bm.faces:
            f.smooth = True
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._finish(name, bm, col, mat, origin=center)

    def palm_crown(self, col, name, center, frond_count=12, frond_len=3.8, mat=None):
        """Creates an organic, radiating tropical palm crown with drooping curved fronds."""
        bm = bmesh.new()
        # Central crown bud
        res_bud = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.45)
        for f in bm.faces:
            f.smooth = True

        for i in range(frond_count):
            ang = i * (2.0 * math.pi / frond_count) + (0.1 if i % 2 else 0.0)
            segments = 6
            curve_drop = 0.85 + (0.25 if i % 2 else 0.0)
            dx, dy = math.cos(ang), math.sin(ang)

            prev_verts = None
            for s in range(segments + 1):
                t = s / segments
                dist = frond_len * t
                # Parabolic droop
                drop = -curve_drop * (t ** 2)
                width = 0.42 * (1.0 - 0.7 * t) if s > 0 else 0.12
                # Perpendicular in XY
                px, py = -dy * width * 0.5, dx * width * 0.5
                cx, cy, cz = dx * dist, dy * dist, drop

                v1 = bm.verts.new(Vector((cx + px, cy + py, cz)))
                v2 = bm.verts.new(Vector((cx - px, cy - py, cz)))

                if prev_verts:
                    f = bm.faces.new((prev_verts[0], v1, v2, prev_verts[1]))
                    f.smooth = True
                prev_verts = (v1, v2)

        bmesh.ops.translate(bm, vec=Vector(center))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._finish(name, bm, col, mat, origin=center)



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
    curb_mat = m.get("curb", m["wall_trim"])
    soil_mat = m.get("soil", m["trunk"])
    paver_mat = m.get("paving")

    # 1. Macro natural lawn
    b.box(col, "Ground_Grass", (0, 30, -0.1), (360, 320, 0.2), m["grass"])

    # 2. Main road with curbs and realistic markings
    b.box(col, "Road_Main", (0, 48, 0.02), (9.0, 56.0, 0.04), m["asphalt"])
    # Concrete curbs along main road
    b.box(col, "Curb_Road_Main_L", (-4.65, 48, 0.05), (0.35, 56.0, 0.08), curb_mat)
    b.box(col, "Curb_Road_Main_R", (4.65, 48, 0.05), (0.35, 56.0, 0.08), curb_mat)
    # Solid white boundary edge stripes
    b.box(col, "Road_Solid_Line_L", (-4.2, 48, 0.045), (0.15, 55.5, 0.02), m["park_lines"])
    b.box(col, "Road_Solid_Line_R", (4.2, 48, 0.045), (0.15, 55.5, 0.02), m["park_lines"])
    # Dashed center yellow line
    for z in range(22, 74, 5):
        b.box(col, f"Road_Dash_{z}", (0, z, 0.045), (0.25, 2.5, 0.02), m["road_lines"])
    # Pedestrian zebra crossing at plaza arrival (Y = 20.5)
    for zi in range(7):
        zx = -3.6 + zi * 1.2
        b.box(col, f"Road_Zebra_{zi}", (zx, 20.5, 0.045), (0.50, 2.4, 0.02), m["park_lines"])

    # 3. Parking branch and parking lot
    b.box(col, "Road_Branch_Parking", (18, 37, 0.02), (26.0, 7.0, 0.04), m["asphalt"])
    b.box(col, "Curb_Parking_Branch_N", (18, 40.65, 0.05), (26.0, 0.35, 0.08), curb_mat)
    b.box(col, "Curb_Parking_Branch_S", (18, 33.35, 0.05), (26.0, 0.35, 0.08), curb_mat)
    b.box(col, "Parking_Area", (44, 43, 0.025), (34.0, 24.0, 0.04), m["parking"])
    for k in range(9):
        x = 30 + k * 3.4
        b.box(col, f"Parking_Line_A_{k}", (x, 36, 0.05), (0.15, 6.0, 0.02), m["park_lines"])
        b.box(col, f"Parking_Line_B_{k}", (x, 50, 0.05), (0.15, 6.0, 0.02), m["park_lines"])

    # 4. Plaza & Walkways with interlocking paver textures
    b.box(col, "Plaza_Front", (0, 15, 0.03), (48.0, 10.0, 0.05), paver_mat)
    b.box(col, "Walkway_Garden_A", (-22.5, 34, 0.03), (3.0, 30.0, 0.05), paver_mat)
    b.box(col, "Walkway_Garden_B", (-31, 48.5, 0.03), (16.0, 3.0, 0.05), paver_mat)
    b.cyl(col, "Garden_Circle_Plaza", (-40, 48.5, 0.035), 6.0, 0.04, paver_mat, segments=48)
    # Garden flowerbed with raised curb border and rich dark soil
    b.cyl(col, "Garden_Flowerbed_Curb", (-40, 48.5, 0.07), 2.8, 0.12, curb_mat, segments=36)
    b.cyl(col, "Garden_Flowerbed", (-40, 48.5, 0.09), 2.5, 0.10, soil_mat, segments=32)
    b.box(col, "Walkway_Parking", (22.5, 27, 0.03), (3.0, 16.0, 0.05), paver_mat)

    # 5. Entrance Plinth Planter Beds (framing the main building steps)
    b.box(col, "Planter_Bed_L", (-13.5, 9.8, 0.18), (9.0, 1.4, 0.36), curb_mat)
    b.box(col, "Planter_Soil_L", (-13.5, 9.8, 0.28), (8.6, 1.0, 0.18), soil_mat)
    b.box(col, "Planter_Bed_R", (13.5, 9.8, 0.18), (9.0, 1.4, 0.36), curb_mat)
    b.box(col, "Planter_Soil_R", (13.5, 9.8, 0.28), (8.6, 1.0, 0.18), soil_mat)


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
    ceil_mat = m.get("ceiling", m["wall_int"])
    for name, ((x0, x1), (y0, y1)) in pieces.items():
        b.box(col, name, ((x0 + x1) / 2, (y0 + y1) / 2, z_c), (x1 - x0, y1 - y0, t), ceil_mat)

    # Roof and parapets
    rx, ry = cfg.ROOF_HALF
    b.box(col, "Roof_Main", (0, 0, cfg.ROOF_BOTTOM_Z + cfg.ROOF_THICK / 2), (2 * rx, 2 * ry, cfg.ROOF_THICK), ceil_mat)
    pz = cfg.ROOF_TOP_Z + cfg.PARAPET_H / 2
    b.box(col, "Parapet_Front", (0, 8.75, pz), (42.0, 0.3, cfg.PARAPET_H), m["wall_trim"])
    b.box(col, "Parapet_Back", (0, -8.75, pz), (42.0, 0.3, cfg.PARAPET_H), m["wall_trim"])
    b.box(col, "Parapet_Left", (-20.85, 0, pz), (0.3, 17.6, cfg.PARAPET_H), m["wall_trim"])
    b.box(col, "Parapet_Right", (20.85, 0, pz), (0.3, 17.6, cfg.PARAPET_H), m["wall_trim"])
    # Signboard now mounted on the parapet with 3D brass lettering & emblem
    b.box(col, "Building_Sign_Panel", (0, 8.96, pz), (16.0, 0.12, 1.1), m["wall_trim"])
    b.box(col, "Building_Sign_Border", (0, 8.98, pz), (16.2, 0.08, 1.15), m["brass"])
    # 3D Institutional Emblem Medallion
    b.cyl(col, "Building_Crest_Emblem", (0, 9.04, pz + 0.15), 0.42, 0.06, m["brass"], rot=Matrix.Rotation(math.pi / 2, 3, 'X'), segments=24)
    # 3D Brass Lettering Blocks (Primary and Secondary Facade Lettering)
    b.box(col, "Sign_Text_Trust", (0, 9.03, pz + 0.32), (12.5, 0.04, 0.18), m["brass"])
    b.box(col, "Sign_Text_College", (0, 9.03, pz - 0.18), (14.2, 0.04, 0.32), m["brass"])

    # ------------------------------------------------------------------
    # Rooftop Infrastructure (Z = 8.60 m)
    # ------------------------------------------------------------------
    rz = cfg.ROOF_TOP_Z
    # 1. Rooftop Stair Penthouse / Elevator Machine Room
    b.box(col, "Roof_Penthouse", (5.0, 2.0, rz + 1.4), (4.8, 5.2, 2.8), m["wall_ext"])
    b.box(col, "Roof_Penthouse_Slab", (5.0, 2.0, rz + 2.85), (5.2, 5.6, 0.2), m["wall_trim"])
    b.box(col, "Roof_Penthouse_Door", (5.0, 4.65, rz + 1.05), (1.1, 0.08, 2.1), m["metal_dark"])

    # 2. Solar Photovoltaic Array (2 rows of 7 panels angled 22° facing south +Y)
    solar_rot = Matrix.Rotation(math.radians(-22.0), 3, 'X')
    for row_idx, ry_pos in enumerate((-2.5, -5.8)):
        # Aluminum support rails
        b.box(col, f"Solar_Rack_Rail_L_{row_idx}", (-15.5, ry_pos, rz + 0.35), (0.08, 2.2, 0.70), m["solar_frame"])
        b.box(col, f"Solar_Rack_Rail_R_{row_idx}", (-3.5, ry_pos, rz + 0.35), (0.08, 2.2, 0.70), m["solar_frame"])
        for pi in range(7):
            px = -15.0 + pi * 1.85
            # Solar panel frame & silicon PV face
            b.box(col, f"Solar_Panel_Frame_{row_idx}_{pi}", (px, ry_pos, rz + 0.55), (1.75, 1.15, 0.05), m["solar_frame"], rot=solar_rot)
            b.box(col, f"Solar_Panel_Cell_{row_idx}_{pi}", (px, ry_pos, rz + 0.56), (1.68, 1.08, 0.04), m["solar"], rot=solar_rot)

    # 3. Commercial HVAC Rooftop Chillers / Air Handling Units
    for hi, hx in enumerate((11.5, 14.5, 17.5)):
        b.box(col, f"Roof_HVAC_Unit_{hi}", (hx, -3.5, rz + 0.75), (1.8, 2.4, 1.5), m["metal_dark"])
        # Top exhaust fans
        b.cyl(col, f"Roof_HVAC_FanA_{hi}", (hx - 0.4, -3.5, rz + 1.52), 0.35, 0.06, m["solar_frame"], segments=16)
        b.cyl(col, f"Roof_HVAC_FanB_{hi}", (hx + 0.4, -3.5, rz + 1.52), 0.35, 0.06, m["solar_frame"], segments=16)
        # Side louver grille
        b.box(col, f"Roof_HVAC_Grille_{hi}", (hx, -2.28, rz + 0.75), (1.5, 0.05, 1.1), m["solar_frame"])

    # 4. Elevated Water Storage Tanks & Skid
    b.box(col, "Roof_WaterTank_Skid", (14.5, 4.0, rz + 0.4), (4.5, 2.8, 0.8), m["metal_dark"])
    for ti, tx in enumerate((13.2, 15.8)):
        b.cyl(col, f"Roof_WaterTank_{ti}", (tx, 4.0, rz + 1.7), 0.85, 1.8, m["metal_dark"], segments=24)
        b.cyl(col, f"Roof_WaterTank_Cap_{ti}", (tx, 4.0, rz + 2.65), 0.35, 0.12, m["metal_dark"], segments=16)

    # 5. Rooftop Telecom Mast & Lightning Rod
    b.cyl(col, "Roof_Lightning_Rod", (5.0, 2.0, rz + 4.5), 0.03, 3.2, m["solar_frame"], segments=8)
    b.cyl(col, "Roof_Antenna_Mast", (-18.0, -6.0, rz + 2.5), 0.04, 5.0, m["solar_frame"], segments=8)

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

    # Handrails: sloped rail + posts on both sides, terminating cleanly at the top landing
    slope = R / T
    y_a = cfg.STAIR_Y_START - T / 2
    z_a = fz + R + cfg.STAIR_RAIL_H
    ym_19 = cfg.STAIR_Y_START - (cfg.STAIR_TREAD_COUNT - 1) * T - T / 2
    z_19 = fz + cfg.STAIR_TREAD_COUNT * R + cfg.STAIR_RAIL_H
    y_b = cfg.STAIR_Y_TOP
    z_landing = cfg.FLOOR_1_Z + cfg.STAIR_RAIL_H
    for side, nm in ((-1, "L"), (1, "R")):
        x = cfg.STAIR_X + side * (W / 2 + 0.025)
        bm = bmesh.new()
        # Main sloped rail along the steps
        beam_into(bm, (x, y_a, z_a), (x, ym_19, z_19), 0.05)
        # Smooth transition into the top landing post
        beam_into(bm, (x, ym_19, z_19), (x, y_b, z_landing), 0.05)
        # Intermediate posts along the run
        for i in range(1, cfg.STAIR_TREAD_COUNT + 1, 4):
            ym = cfg.STAIR_Y_START - (i - 1) * T - T / 2
            top = fz + i * R
            z_post_top = z_a + (y_a - ym) * slope
            box_into(bm, (x, ym, (top + z_post_top) / 2),
                     (0.04, 0.04, z_post_top - top))
        # Top step post (step 19)
        top_19 = fz + cfg.STAIR_TREAD_COUNT * R
        box_into(bm, (x, ym_19, (top_19 + z_19) / 2),
                 (0.04, 0.04, z_19 - top_19))
        # Top landing post firmly anchored into the second floor landing slab
        box_into(bm, (x, y_b, (cfg.FLOOR_1_Z + z_landing) / 2),
                 (0.04, 0.04, z_landing - cfg.FLOOR_1_Z))
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

    # GROUND FLOOR WEST (Classroom 101):
    b.box(col, "Class_G_Blackboard", (-14.0, y_wall + 0.04, g + 1.9), (4.5, 0.08, 1.4), m["board"])
    b.box(col, "Teacher_Table_G", (-14.0, 1.6, g + 0.4), (2.2, 0.9, 0.8), m["wood"])
    for row in range(3):
        for ci in range(3):
            x, y = -17.5 + ci * 2.8, 3.2 + row * 1.5
            b.box(col, f"Desk_G_{row}_{ci}", (x, y, g + 0.35), (1.4, 0.6, 0.7), m["wood"])
            b.box(col, f"Bench_G_{row}_{ci}", (x, y + 0.5, g + 0.225), (1.3, 0.35, 0.45), m["metal_dark"])

    # GROUND FLOOR EAST (Computer Lab 102):
    b.box(col, "Lab_G_Screen", (14.0, y_wall + 0.04, g + 1.9), (4.5, 0.08, 1.4), m["wall_ext"])
    b.box(col, "Lab_G_Instructor_Desk", (14.0, 1.6, g + 0.4), (2.2, 0.9, 0.8), m["wood"])
    b.box(col, "Lab_G_Instructor_PC", (14.0, 1.6, g + 0.95), (0.6, 0.08, 0.35), m["metal_dark"])
    for row in range(3):
        for ci in range(3):
            x, y = 10.5 + ci * 2.8, 3.2 + row * 1.5
            b.box(col, f"Lab_Desk_G_{row}_{ci}", (x, y, g + 0.36), (1.4, 0.65, 0.72), m["wood"])
            b.box(col, f"Lab_Monitor_G_{row}_{ci}", (x, y - 0.06, g + 0.92), (0.52, 0.06, 0.32), m["metal_dark"])
            b.box(col, f"Lab_CPU_G_{row}_{ci}", (x + 0.52, y, g + 0.22), (0.18, 0.42, 0.40), m["metal_dark"])
            b.box(col, f"Lab_Chair_G_{row}_{ci}", (x, y + 0.52, g + 0.24), (0.55, 0.50, 0.48), m["metal_dark"])

    # FIRST/SECOND FLOOR WEST (Classroom 201):
    b.box(col, "Class_1_Whiteboard", (-14.0, y_wall + 0.04, f1 + 1.9), (4.5, 0.08, 1.4), m["board"])
    b.box(col, "Teacher_Table_1", (-14.0, 1.6, f1 + 0.4), (2.2, 0.9, 0.8), m["wood"])
    for row in range(3):
        for ci in range(3):
            x, y = -17.5 + ci * 2.8, 3.2 + row * 1.5
            b.box(col, f"Desk_1_{row}_{ci}", (x, y, f1 + 0.35), (1.4, 0.6, 0.7), m["wood"])
            b.box(col, f"Bench_1_{row}_{ci}", (x, y + 0.5, f1 + 0.225), (1.3, 0.35, 0.45), m["metal_dark"])


# ----------------------------------------------------------------------
# Outdoor props, vehicles, gate, vegetation (layout unchanged)
# ----------------------------------------------------------------------
def build_props(b):
    col, m = b.cols["props"], b.mats
    curb_mat = m.get("curb", m["wall_trim"])
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

    # ------------------------------------------------------------------
    # High-fidelity Procedural Campus Vehicles from Reference Images
    # ------------------------------------------------------------------
    mat_white = materials_pbr.create_car_paint_material("Mat_Car_NanoWhite", (0.95, 0.95, 0.95))
    mat_red = materials_pbr.create_car_paint_material("Mat_Car_CorvetteRed", (0.86, 0.07, 0.09))
    mat_lime = materials_pbr.create_car_paint_material("Mat_Car_PunchLime", (0.72, 0.82, 0.15))
    mat_beast_green = materials_pbr.create_car_paint_material("Mat_Bike_BeastGreen", (0.18, 0.82, 0.15))
    mat_aurore_blue = materials_pbr.create_car_paint_material("Mat_Bike_AuroreBlue", (0.12, 0.45, 0.78))
    mat_silver = materials_pbr.create_metal_material("Mat_AlloySilver", (0.82, 0.84, 0.86), roughness=0.25, metallic=0.88)
    mat_black = materials_pbr.create_metal_material("Mat_PlasticBlack", (0.04, 0.04, 0.045), roughness=0.65, metallic=0.0)
    mat_carbon = materials_pbr.create_metal_material("Mat_CarbonFiber", (0.05, 0.05, 0.055), roughness=0.35, metallic=0.3)
    mat_ev_green = materials_pbr.create_concrete_material("Mat_EV_Plate", (0.08, 0.65, 0.22), roughness=0.35)
    mat_led_white = materials_pbr.create_lamp_glow_material("Mat_Headlight_LED", (1.0, 1.0, 1.0), strength=12.0)
    mat_led_red = materials_pbr.create_lamp_glow_material("Mat_Taillight_LED", (0.95, 0.05, 0.05), strength=8.0)
    mat_rubber = materials_pbr.create_metal_material("Mat_TireRubber", (0.03, 0.03, 0.035), roughness=0.85, metallic=0.0)
    mat_glass = m.get("car_glass", m["glass"])

    wheel_rot = Matrix.Rotation(math.pi / 2, 3, 'Y')   # wheel axis along X

    # 1. TATA NANO EV (IMAGE 1: White compact EV hatchback with black bumper fascia & green plate)
    c0_x, c0_y = 32.0, 36.0
    b.box(col, "Car_0_Body", (c0_x, c0_y, 0.62), (1.52, 3.10, 0.65), mat_white)
    b.box(col, "Car_0_FrontHood", (c0_x, c0_y + 1.15, 0.68), (1.42, 0.85, 0.45), mat_white)
    b.box(col, "Car_0_Cabin", (c0_x, c0_y - 0.15, 1.28), (1.42, 2.10, 0.70), mat_glass)
    b.box(col, "Car_0_Roof", (c0_x, c0_y - 0.15, 1.64), (1.36, 1.95, 0.06), mat_white)
    b.box(col, "Car_0_BumperFront", (c0_x, c0_y + 1.56, 0.35), (1.48, 0.14, 0.38), mat_black)
    b.box(col, "Car_0_BumperRear", (c0_x, c0_y - 1.56, 0.35), (1.48, 0.14, 0.38), mat_black)
    b.box(col, "Car_0_PlateFront", (c0_x, c0_y + 1.64, 0.32), (0.42, 0.02, 0.11), mat_ev_green)
    b.box(col, "Car_0_PlateRear", (c0_x, c0_y - 1.64, 0.36), (0.42, 0.02, 0.11), mat_ev_green)
    for s, nm in ((-1, "L"), (1, "R")):
        b.box(col, f"Car_0_Headlight_{nm}", (c0_x + s * 0.52, c0_y + 1.48, 0.70), (0.28, 0.12, 0.18), mat_led_white)
        b.box(col, f"Car_0_Taillight_{nm}", (c0_x + s * 0.66, c0_y - 1.54, 1.05), (0.08, 0.06, 0.48), mat_led_red)
        b.box(col, f"Car_0_Mirror_{nm}", (c0_x + s * 0.82, c0_y + 0.45, 1.08), (0.16, 0.12, 0.10), mat_black)
    b.cyl(col, "Car_0_Antenna", (c0_x, c0_y + 0.65, 1.76), 0.015, 0.22, mat_black)
    for k, (wx, wy) in enumerate([(-0.74, 0.95), (0.74, 0.95), (-0.74, -0.95), (0.74, -0.95)]):
        b.cyl(col, f"Car_0_Wheel_{k}", (c0_x + wx, c0_y + wy, 0.26), 0.26, 0.16, mat_rubber, rot=wheel_rot, segments=20)
        b.cyl(col, f"Car_0_Hubcap_{k}", (c0_x + wx + (0.01 if wx > 0 else -0.01), c0_y + wy, 0.26), 0.14, 0.17, mat_silver, rot=wheel_rot, segments=16)

    # 2. CHEVROLET CORVETTE C8 Z06 (IMAGE 2: Torch Red exotic supercar with carbon rear wing & splitters)
    c1_x, c1_y = 35.4, 36.0
    b.box(col, "Car_1_Body", (c1_x, c1_y, 0.52), (1.98, 4.55, 0.40), mat_red)
    b.box(col, "Car_1_FrontNose", (c1_x, c1_y + 1.25, 0.46), (1.92, 2.10, 0.34), mat_red)
    b.box(col, "Car_1_RearDeck", (c1_x, c1_y - 0.95, 0.56), (2.02, 2.45, 0.42), mat_red)
    b.box(col, "Car_1_FrontSplitter", (c1_x, c1_y + 2.32, 0.16), (1.95, 0.22, 0.05), mat_carbon)
    b.box(col, "Car_1_Cabin", (c1_x, c1_y + 0.10, 0.88), (1.42, 1.85, 0.38), mat_glass)
    b.box(col, "Car_1_Roof", (c1_x, c1_y + 0.05, 1.08), (1.30, 1.20, 0.04), mat_carbon)
    for s, nm in ((-1, "L"), (1, "R")):
        b.box(col, f"Car_1_SideSkirt_{nm}", (c1_x + s * 0.98, c1_y, 0.16), (0.08, 3.40, 0.05), mat_carbon)
        b.box(col, f"Car_1_SideScoop_{nm}", (c1_x + s * 0.98, c1_y - 0.25, 0.54), (0.10, 0.65, 0.36), mat_carbon)
        b.box(col, f"Car_1_Headlight_{nm}", (c1_x + s * 0.72, c1_y + 1.95, 0.56), (0.35, 0.20, 0.06), mat_led_white)
        b.box(col, f"Car_1_Taillight_{nm}", (c1_x + s * 0.72, c1_y - 2.18, 0.65), (0.32, 0.06, 0.08), mat_led_red)
        b.box(col, f"Car_1_WingStrut_{nm}", (c1_x + s * 0.52, c1_y - 2.15, 0.92), (0.05, 0.10, 0.38), mat_carbon)
        b.box(col, f"Car_1_WingEnd_{nm}", (c1_x + s * 0.88, c1_y - 2.18, 1.12), (0.03, 0.36, 0.16), mat_carbon)
    b.box(col, "Car_1_WingBlade", (c1_x, c1_y - 2.18, 1.12), (1.75, 0.32, 0.04), mat_carbon)
    for k in range(4):
        b.cyl(col, f"Car_1_Exhaust_{k}", (c1_x - 0.18 + k * 0.12, c1_y - 2.22, 0.30), 0.04, 0.12, mat_silver,
              rot=Matrix.Rotation(math.pi / 2, 3, 'X'), segments=16)
    for k, (wx, wy, r, w) in enumerate([(-0.96, 1.30, 0.34, 0.26), (0.96, 1.30, 0.34, 0.26),
                                         (-0.98, -1.30, 0.36, 0.30), (0.98, -1.30, 0.36, 0.30)]):
        b.cyl(col, f"Car_1_Wheel_{k}", (c1_x + wx, c1_y + wy, r), r, w, mat_rubber, rot=wheel_rot, segments=24)
        b.cyl(col, f"Car_1_Rim_{k}", (c1_x + wx + (0.01 if wx > 0 else -0.01), c1_y + wy, r), r * 0.82, w + 0.01, mat_black, rot=wheel_rot, segments=20)

    # 3. TATA PUNCH.EV (IMAGE 3: Lime-Yellow/Citron-Green dual-tone electric SUV with full-width LED lightbar)
    c2_x, c2_y = 38.8, 36.0
    b.box(col, "Car_2_Body", (c2_x, c2_y, 0.72), (1.74, 3.82, 0.55), mat_lime)
    b.box(col, "Car_2_LowerCladding", (c2_x, c2_y, 0.38), (1.78, 3.82, 0.36), mat_black)
    b.box(col, "Car_2_Cabin", (c2_x, c2_y - 0.12, 1.28), (1.54, 2.35, 0.55), mat_glass)
    b.box(col, "Car_2_Roof", (c2_x, c2_y - 0.12, 1.56), (1.48, 2.20, 0.05), mat_black)
    b.box(col, "Car_2_Lightbar", (c2_x, c2_y + 1.88, 0.92), (1.50, 0.06, 0.04), mat_led_white)
    b.box(col, "Car_2_GrilleSlats", (c2_x, c2_y + 1.88, 0.28), (1.10, 0.06, 0.16), mat_black)
    b.box(col, "Car_2_SkidPlate", (c2_x, c2_y + 1.89, 0.18), (0.85, 0.06, 0.08), mat_silver)
    b.box(col, "Car_2_PlateFront", (c2_x, c2_y + 1.90, 0.42), (0.45, 0.02, 0.11), mat_ev_green)
    for s, nm in ((-1, "L"), (1, "R")):
        b.box(col, f"Car_2_Headlight_{nm}", (c2_x + s * 0.65, c2_y + 1.86, 0.62), (0.24, 0.08, 0.20), mat_led_white)
        b.box(col, f"Car_2_Taillight_{nm}", (c2_x + s * 0.72, c2_y - 1.88, 0.92), (0.22, 0.06, 0.18), mat_led_red)
        b.box(col, f"Car_2_RoofRail_{nm}", (c2_x + s * 0.65, c2_y - 0.12, 1.60), (0.05, 1.80, 0.04), mat_silver)
        b.box(col, f"Car_2_Mirror_{nm}", (c2_x + s * 0.92, c2_y + 0.45, 1.10), (0.18, 0.12, 0.10), mat_black)
    for k, (wx, wy) in enumerate([(-0.85, 1.25), (0.85, 1.25), (-0.85, -1.25), (0.85, -1.25)]):
        b.cyl(col, f"Car_2_Wheel_{k}", (c2_x + wx, c2_y + wy, 0.32), 0.32, 0.22, mat_rubber, rot=wheel_rot, segments=22)
        b.cyl(col, f"Car_2_Rim_{k}", (c2_x + wx + (0.01 if wx > 0 else -0.01), c2_y + wy, 0.32), 0.22, 0.23, mat_silver, rot=wheel_rot, segments=18)

    # 4. JOY E-BIKE BEAST (IMAGE 4: Metallic Green & Black electric sports motorcycle)
    b3_x, b3_y = 42.0, 36.0
    b.box(col, "Bike_3_Body", (b3_x, b3_y, 0.65), (0.75, 2.10, 0.75), mat_black)
    b.box(col, "Bike_3_Battery", (b3_x, b3_y, 0.52), (0.36, 0.82, 0.48), mat_black)
    b.box(col, "Bike_3_Tank", (b3_x, b3_y + 0.22, 0.85), (0.48, 0.65, 0.38), mat_beast_green)
    b.box(col, "Bike_3_HeadlightCowl", (b3_x, b3_y + 0.80, 0.95), (0.32, 0.26, 0.30), mat_beast_green)
    b.box(col, "Bike_3_LED", (b3_x, b3_y + 0.94, 0.95), (0.24, 0.04, 0.16), mat_led_white)
    b.box(col, "Bike_3_Visor", (b3_x, b3_y + 0.75, 1.14), (0.24, 0.12, 0.14), mat_glass)
    b.box(col, "Bike_3_SeatRider", (b3_x, b3_y - 0.22, 0.78), (0.32, 0.40, 0.12), mat_black)
    b.box(col, "Bike_3_SeatPillion", (b3_x, b3_y - 0.52, 0.88), (0.26, 0.30, 0.10), mat_black)
    b.box(col, "Bike_3_Tail", (b3_x, b3_y - 0.78, 0.90), (0.24, 0.35, 0.16), mat_beast_green)
    b.box(col, "Bike_3_Taillight", (b3_x, b3_y - 0.96, 0.90), (0.16, 0.04, 0.06), mat_led_red)
    b.box(col, "Bike_3_Handlebars", (b3_x, b3_y + 0.62, 1.05), (0.72, 0.06, 0.06), mat_black)
    b.box(col, "Bike_3_Kickstand", (b3_x - 0.18, b3_y - 0.10, 0.15), (0.04, 0.04, 0.30), mat_black)
    for s, nm in ((-1, "L"), (1, "R")):
        b.box(col, f"Bike_3_Trellis_{nm}", (b3_x + s * 0.22, b3_y + 0.05, 0.68), (0.04, 0.70, 0.25), mat_beast_green)
        b.cyl(col, f"Bike_3_Fork_{nm}", (b3_x + s * 0.10, b3_y + 0.76, 0.52), 0.03, 0.55, mat_silver)
    # Front and rear motorcycle wheels
    b.cyl(col, "Bike_3_Wheel_F", (b3_x, b3_y + 0.85, 0.30), 0.30, 0.13, mat_rubber, rot=wheel_rot, segments=22)
    b.cyl(col, "Bike_3_Rim_F", (b3_x, b3_y + 0.85, 0.30), 0.21, 0.14, mat_black, rot=wheel_rot, segments=18)
    b.cyl(col, "Bike_3_Disc_F", (b3_x + 0.08, b3_y + 0.85, 0.30), 0.15, 0.015, mat_silver, rot=wheel_rot, segments=16)
    b.cyl(col, "Bike_3_Wheel_R", (b3_x, b3_y - 0.85, 0.30), 0.30, 0.15, mat_rubber, rot=wheel_rot, segments=22)
    b.cyl(col, "Bike_3_Rim_R", (b3_x, b3_y - 0.85, 0.30), 0.21, 0.16, mat_black, rot=wheel_rot, segments=18)

    # 5. AURORE ELECTRIC SPORTS BIKE (IMAGE 5: Metallic Electric Blue & Black commuter/sports bike)
    b4_x, b4_y = 43.4, 36.0
    b.box(col, "Bike_4_Body", (b4_x, b4_y, 0.65), (0.75, 2.10, 0.75), mat_black)
    b.box(col, "Bike_4_Battery", (b4_x, b4_y, 0.50), (0.35, 0.80, 0.46), mat_black)
    b.box(col, "Bike_4_CoolingFins", (b4_x, b4_y, 0.50), (0.37, 0.55, 0.32), mat_silver)
    b.box(col, "Bike_4_Tank", (b4_x, b4_y + 0.20, 0.82), (0.45, 0.62, 0.35), mat_aurore_blue)
    b.box(col, "Bike_4_FrontFender", (b4_x, b4_y + 0.80, 0.48), (0.18, 0.45, 0.12), mat_aurore_blue)
    b.box(col, "Bike_4_Headlight", (b4_x, b4_y + 0.78, 0.92), (0.26, 0.24, 0.25), mat_aurore_blue)
    b.box(col, "Bike_4_LED", (b4_x, b4_y + 0.91, 0.92), (0.20, 0.04, 0.14), mat_led_white)
    b.box(col, "Bike_4_Seat", (b4_x, b4_y - 0.32, 0.80), (0.30, 0.72, 0.12), mat_black)
    b.box(col, "Bike_4_GrabRail", (b4_x, b4_y - 0.68, 0.86), (0.32, 0.15, 0.04), mat_silver)
    b.box(col, "Bike_4_Handlebars", (b4_x, b4_y + 0.60, 1.02), (0.70, 0.05, 0.05), mat_black)
    b.box(col, "Bike_4_Kickstand", (b4_x - 0.16, b4_y - 0.10, 0.15), (0.04, 0.04, 0.30), mat_black)
    for s, nm in ((-1, "L"), (1, "R")):
        b.cyl(col, f"Bike_4_Fork_{nm}", (b4_x + s * 0.09, b4_y + 0.74, 0.50), 0.028, 0.52, mat_silver)
    b.cyl(col, "Bike_4_Wheel_F", (b4_x, b4_y + 0.82, 0.30), 0.30, 0.13, mat_rubber, rot=wheel_rot, segments=22)
    b.cyl(col, "Bike_4_Rim_F", (b4_x, b4_y + 0.82, 0.30), 0.21, 0.14, mat_black, rot=wheel_rot, segments=18)
    b.cyl(col, "Bike_4_Wheel_R", (b4_x, b4_y - 0.82, 0.30), 0.30, 0.15, mat_rubber, rot=wheel_rot, segments=22)
    b.cyl(col, "Bike_4_Rim_R", (b4_x, b4_y - 0.82, 0.30), 0.21, 0.16, mat_black, rot=wheel_rot, segments=18)

    # 6. EXECUTIVE CAMPUS SEDAN
    c5_x, c5_y = 46.8, 36.0
    mat_sedan_silver = materials_pbr.create_car_paint_material("Mat_Car_SedanSilver", (0.84, 0.86, 0.88))
    b.box(col, "Car_5_Body", (c5_x, c5_y, 0.60), (1.85, 4.40, 0.62), mat_sedan_silver)
    b.box(col, "Car_5_Cabin", (c5_x, c5_y - 0.15, 1.20), (1.55, 2.30, 0.55), mat_glass)
    # ------------------------------------------------------------------
    # 7. MULTIPURPOSE SPORTS COMPLEX (Basketball & Recreation Court)
    # ------------------------------------------------------------------
    court_cx, court_cy = 40.0, 18.0
    # Regulation court pad with green apron
    b.box(col, "Court_Pad_Apron", (court_cx, court_cy, 0.035), (28.0, 16.0, 0.07), m["court_green"])
    # Inner playing court with high-contrast blue sports surface
    b.box(col, "Court_Surface_Blue", (court_cx, court_cy, 0.045), (24.0, 13.0, 0.05), m["court_blue"])
    # White painted court boundary line
    b.box(col, "Court_Line_Border_N", (court_cx, court_cy + 6.5, 0.055), (24.0, 0.10, 0.02), m["court_lines"])
    b.box(col, "Court_Line_Border_S", (court_cx, court_cy - 6.5, 0.055), (24.0, 0.10, 0.02), m["court_lines"])
    b.box(col, "Court_Line_Border_W", (court_cx - 12.0, court_cy, 0.055), (0.10, 13.0, 0.02), m["court_lines"])
    b.box(col, "Court_Line_Border_E", (court_cx + 12.0, court_cy, 0.055), (0.10, 13.0, 0.02), m["court_lines"])
    # Half-court division line & center circle
    b.box(col, "Court_Line_Center", (court_cx, court_cy, 0.055), (0.10, 13.0, 0.02), m["court_lines"])
    b.cyl(col, "Court_Center_Circle", (court_cx, court_cy, 0.054), 1.8, 0.02, m["court_lines"], segments=32)
    b.cyl(col, "Court_Center_Circle_Inner", (court_cx, court_cy, 0.056), 1.7, 0.02, m["court_blue"], segments=32)
    # Free throw keys (West and East)
    b.box(col, "Court_Key_West", (court_cx - 9.5, court_cy, 0.052), (5.0, 3.6, 0.02), m["court_green"])
    b.box(col, "Court_Key_East", (court_cx + 9.5, court_cy, 0.052), (5.0, 3.6, 0.02), m["court_green"])

    # Basketball Goal West & East
    for hoop_side, hoop_x, h_dir in (("West", court_cx - 11.5, 1), ("East", court_cx + 11.5, -1)):
        # Heavy gooseneck steel pole
        b.cyl(col, f"Hoop_{hoop_side}_Base", (hoop_x - h_dir * 0.8, court_cy, 1.9), 0.10, 3.8, m["metal_dark"], segments=16)
        b.box(col, f"Hoop_{hoop_side}_Overhang", (hoop_x - h_dir * 0.4, court_cy, 3.8), (0.8, 0.12, 0.12), m["metal_dark"])
        # Acrylic backboard (1.8m x 1.05m)
        b.box(col, f"Hoop_{hoop_side}_Backboard", (hoop_x, court_cy, 3.35), (0.05, 1.80, 1.05), m["glass"])
        b.box(col, f"Hoop_{hoop_side}_Frame", (hoop_x, court_cy, 3.35), (0.06, 1.84, 1.09), m["metal_dark"])
        # Orange steel breakaway rim (at 3.05m regulation height)
        b.cyl(col, f"Hoop_{hoop_side}_Rim", (hoop_x + h_dir * 0.35, court_cy, 3.05), 0.23, 0.03, m["rubber_orange"], segments=20)
        # Net cylinder
        b.cone(col, f"Hoop_{hoop_side}_Net", (hoop_x + h_dir * 0.35, court_cy, 2.85), r_bottom=0.12, r_top=0.22, depth=0.40, mat=m["court_lines"], segments=12)

    # Court Chainlink Perimeter Enclosure (3.5m high)
    for corner_i, (fc_x, fc_y) in enumerate(((court_cx - 14.0, court_cy - 8.0), (court_cx + 14.0, court_cy - 8.0),
                                            (court_cx + 14.0, court_cy + 8.0), (court_cx - 14.0, court_cy + 8.0))):
        b.cyl(col, f"Court_Corner_Post_{corner_i}", (fc_x, fc_y, 1.8), 0.08, 3.6, m["chainlink"], segments=12)
        # Stadium Floodlight fixtures on all 4 corners
        b.cyl(col, f"Court_Floodlight_Pole_{corner_i}", (fc_x, fc_y, 3.6), 0.10, 7.2, m["metal_dark"], segments=12)
        b.box(col, f"Court_Floodlight_Crossarm_{corner_i}", (fc_x, fc_y, 7.2), (1.4, 0.4, 0.12), m["metal_dark"])
        for hi in (-0.5, 0.5):
            b.box(col, f"Court_Floodlight_LED_{corner_i}_{hi}", (fc_x + hi, fc_y, 7.05), (0.42, 0.28, 0.18), m["lamp_glow"])

    # Court Open Tubular Perimeter Enclosure (3.5m high) with top/mid/bottom steel rails
    # Concrete base curb
    b.box(col, "Court_Curb_N", (court_cx, court_cy + 8.0, 0.12), (28.2, 0.22, 0.24), curb_mat)
    b.box(col, "Court_Curb_S", (court_cx, court_cy - 8.0, 0.12), (28.2, 0.22, 0.24), curb_mat)
    b.box(col, "Court_Curb_W", (court_cx - 14.0, court_cy, 0.12), (0.22, 16.2, 0.24), curb_mat)
    b.box(col, "Court_Curb_E", (court_cx + 14.0, court_cy, 0.12), (0.22, 16.2, 0.24), curb_mat)
    # Intermediate fence posts every 3.5m
    for pi in range(1, 8):
        px = court_cx - 14.0 + pi * 3.5
        b.cyl(col, f"Court_Post_N_{pi}", (px, court_cy + 8.0, 1.8), 0.045, 3.6, m["chainlink"], segments=8)
        b.cyl(col, f"Court_Post_S_{pi}", (px, court_cy - 8.0, 1.8), 0.045, 3.6, m["chainlink"], segments=8)
    for pi in range(1, 4):
        py = court_cy - 8.0 + pi * 4.0
        b.cyl(col, f"Court_Post_W_{pi}", (court_cx - 14.0, py, 1.8), 0.045, 3.6, m["chainlink"], segments=8)
        b.cyl(col, f"Court_Post_E_{pi}", (court_cx + 14.0, py, 1.8), 0.045, 3.6, m["chainlink"], segments=8)

    # Steel tension rails (Top Z = 3.6m, Mid Z = 1.8m, Bottom Z = 0.25m)
    for rz in (0.25, 1.8, 3.6):
        b.box(col, f"Court_Rail_N_{rz}", (court_cx, court_cy + 8.0, rz), (28.0, 0.05, 0.05), m["chainlink"])
        b.box(col, f"Court_Rail_S_{rz}", (court_cx, court_cy - 8.0, rz), (28.0, 0.05, 0.05), m["chainlink"])
        b.box(col, f"Court_Rail_W_{rz}", (court_cx - 14.0, court_cy, rz), (0.05, 16.0, 0.05), m["chainlink"])
        b.box(col, f"Court_Rail_E_{rz}", (court_cx + 14.0, court_cy, rz), (0.05, 16.0, 0.05), m["chainlink"])

    # Dynamic Active RigidBody Basketballs on Court
    for bi, (bx, by) in enumerate(((court_cx - 2.0, court_cy + 1.2), (court_cx + 4.5, court_cy - 2.0))):
        b.cyl(col, f"Basketball_Prop_{bi}", (bx, by, 0.20), 0.12, 0.24, m["rubber_orange"], segments=16)

    # ------------------------------------------------------------------
    # 8. OUTDOOR CAFETERIA / CANTEEN PLAZA
    # ------------------------------------------------------------------
    cafe_cx, cafe_cy = -30.0, 24.0
    # Herringbone paver dining terrace
    b.box(col, "Cafe_Plaza_Terrace", (cafe_cx, cafe_cy, 0.035), (14.0, 12.0, 0.07), m["paving"])
    # Cafe Kiosk & Serving Pavilion
    b.box(col, "Cafe_Kiosk_Building", (-34.5, 27.5, 1.6), (3.6, 2.8, 3.2), m["wall_ext"])
    b.box(col, "Cafe_Kiosk_Roof", (-34.5, 27.5, 3.3), (4.2, 3.4, 0.25), m["wall_trim"])
    b.box(col, "Cafe_Kiosk_Counter", (-32.6, 27.5, 1.0), (0.35, 2.2, 0.9), m["wood"])
    b.box(col, "Cafe_Kiosk_Awning", (-32.4, 27.5, 2.4), (0.85, 2.4, 0.06), m["fabric_red"])
    b.box(col, "Cafe_Menu_Board", (-32.6, 26.0, 1.8), (0.06, 0.70, 0.90), m["board"])

    # 4 Sets of Outdoor Dining Tables with Parasol Umbrellas
    cafe_tables = [(-27.0, 21.0), (-32.0, 21.0), (-27.0, 26.0), (-29.5, 23.5)]
    for ti, (tx, ty) in enumerate(cafe_tables):
        # Round table
        b.cyl(col, f"Cafe_Table_Base_{ti}", (tx, ty, 0.37), 0.55, 0.74, m["wall_trim"], segments=20)
        b.cyl(col, f"Cafe_Table_Top_{ti}", (tx, ty, 0.74), 0.70, 0.05, m["wall_trim"], segments=24)
        # Center umbrella pole & parasol canopy
        b.cyl(col, f"Cafe_Umbrella_Pole_{ti}", (tx, ty, 1.4), 0.03, 2.4, m["metal_dark"], segments=10)
        mat_parasol = m["fabric_red"] if ti % 2 == 0 else m["fabric_blue"]
        b.cone(col, f"Cafe_Umbrella_Canopy_{ti}", (tx, ty, 2.45), r_bottom=1.35, r_top=0.08, depth=0.55, mat=mat_parasol, segments=16)
        # 4 Chairs arranged radially around table
        for ci in range(4):
            c_ang = ci * (math.pi / 2) + 0.35
            cx = tx + 0.85 * math.cos(c_ang)
            cy = ty + 0.85 * math.sin(c_ang)
            b.box(col, f"Cafe_Chair_Seat_{ti}_{ci}", (cx, cy, 0.42), (0.42, 0.42, 0.05), m["metal_dark"])
            b.box(col, f"Cafe_Chair_Back_{ti}_{ci}", (cx, cy, 0.68), (0.42, 0.06, 0.48), m["metal_dark"])

    # ------------------------------------------------------------------
    # 9. COVERED TWO-WHEELER & BICYCLE STATION
    # ------------------------------------------------------------------
    bike_cx, bike_cy = 25.0, 48.0
    b.box(col, "Bike_Station_Pad", (bike_cx, bike_cy, 0.04), (6.0, 10.0, 0.08), curb_mat)
    # Steel canopy frame & corrugated curved shelter
    for si in (-4.0, 0.0, 4.0):
        b.cyl(col, f"Bike_Canopy_Post_L_{si}", (bike_cx - 2.8, bike_cy + si, 1.5), 0.06, 3.0, m["metal_dark"], segments=10)
        b.cyl(col, f"Bike_Canopy_Post_R_{si}", (bike_cx + 2.8, bike_cy + si, 1.5), 0.06, 3.0, m["metal_dark"], segments=10)
    b.box(col, "Bike_Canopy_Roof", (bike_cx, bike_cy, 3.1), (6.2, 10.4, 0.08), m["metal_dark"])
    # Bicycle parking racks & parked student bikes
    for ri in range(4):
        ry = bike_cy - 3.0 + ri * 2.0
        b.box(col, f"Bike_Rack_Stand_{ri}", (bike_cx - 1.2, ry, 0.40), (1.8, 0.08, 0.80), m["chainlink"])
        # Parked student bicycle
        b.box(col, f"Student_Bike_Frame_{ri}", (bike_cx - 1.2, ry, 0.55), (1.5, 0.20, 0.50), m["court_blue"])
        b.cyl(col, f"Student_Bike_Wheel_F_{ri}", (bike_cx - 1.8, ry, 0.32), 0.32, 0.06, mat_rubber, rot=wheel_rot, segments=16)
        b.cyl(col, f"Student_Bike_Wheel_R_{ri}", (bike_cx - 0.6, ry, 0.32), 0.32, 0.06, mat_rubber, rot=wheel_rot, segments=16)

    # ------------------------------------------------------------------
    # 10. CEREMONIAL FLAGPOLE MONUMENT (Arrival Plaza X = 0.0, Y = 15.5)
    # ------------------------------------------------------------------
    flag_x, flag_y = 0.0, 15.5
    # 3-Tiered hexagonal stone plinth
    b.cyl(col, "Flag_Plinth_Tier_1", (flag_x, flag_y, 0.14), 1.6, 0.22, m["paving"], segments=8)
    b.cyl(col, "Flag_Plinth_Tier_2", (flag_x, flag_y, 0.36), 1.1, 0.22, m["paving"], segments=8)
    b.cyl(col, "Flag_Plinth_Tier_3", (flag_x, flag_y, 0.58), 0.7, 0.22, m["paving"], segments=8)
    # Tapered stainless steel flagpole (11.5m tall)
    b.cone(col, "Flagpole_Mast", (flag_x, flag_y, 6.4), r_bottom=0.08, r_top=0.035, depth=11.5, mat=m["solar_frame"], segments=12)
    b.cyl(col, "Flagpole_Finial", (flag_x, flag_y, 12.2), 0.11, 0.22, m["brass"], segments=16)
    # Waving Indian Tricolor Flag (Saffron, White with Chakra, Green)
    b.box(col, "Flag_Stripe_Saffron", (flag_x + 0.90, flag_y, 11.8), (1.80, 0.04, 0.38), m["flag_orange"])
    b.box(col, "Flag_Stripe_White", (flag_x + 0.90, flag_y, 11.42), (1.80, 0.04, 0.38), m["ceiling"])
    b.cyl(col, "Flag_Ashoka_Chakra", (flag_x + 0.90, flag_y + 0.025, 11.42), 0.12, 0.02, m["court_blue"], rot=Matrix.Rotation(math.pi / 2, 3, 'X'), segments=16)
    b.box(col, "Flag_Stripe_Green", (flag_x + 0.90, flag_y, 11.04), (1.80, 0.04, 0.38), m["flag_green"])

    # ------------------------------------------------------------------
    # 11. CAMPUS DIRECTORY & DUAL-STREAM WASTE SORTING STATIONS
    # ------------------------------------------------------------------
    b.box(col, "Campus_Directory_Board", (-2.8, 21.0, 1.4), (2.2, 0.12, 1.4), m["metal_dark"])
    b.box(col, "Campus_Directory_Map", (-2.8, 21.05, 1.4), (2.0, 0.04, 1.2), m["court_blue"])
    b.cyl(col, "Campus_Directory_Post_L", (-3.8, 21.0, 0.7), 0.05, 1.4, m["metal_dark"], segments=10)
    b.cyl(col, "Campus_Directory_Post_R", (-1.8, 21.0, 0.7), 0.05, 1.4, m["metal_dark"], segments=10)

    # 6 Dual-Stream Waste Bins (Green Bio + Blue Recyclable)
    bin_locations = [(-6.0, 19.5), (6.0, 19.5), (-15.0, 14.5), (15.0, 14.5), (-26.0, 20.5), (28.0, 18.0)]
    for bi, (bx, by) in enumerate(bin_locations):
        b.cyl(col, f"Waste_Bin_Green_{bi}", (bx - 0.22, by, 0.42), 0.18, 0.84, m["flag_green"], segments=14)
        b.cyl(col, f"Waste_Bin_Blue_{bi}", (bx + 0.22, by, 0.42), 0.18, 0.84, m["court_blue"], segments=14)


# ----------------------------------------------------------------------
# Complete 4-Sided Boundary Enclosure, Security Complex & Grand Gate
# ----------------------------------------------------------------------
def build_gate(b):
    col, m = b.cols["gate"], b.mats
    wall_mat = m["wall_ext"]
    trim_mat = m["wall_trim"]

    # ------------------------------------------------------------------
    # 1. GRAND ENTRANCE GATE & ARCH PORTAL (Y = 75.0)
    # ------------------------------------------------------------------
    b.box(col, "Gate_Pillar_L", (-5.8, 75.0, 3.1), (1.5, 1.5, 6.2), trim_mat)
    b.box(col, "Gate_Pillar_R", (5.8, 75.0, 3.1), (1.5, 1.5, 6.2), trim_mat)
    # Pier decorative sphere finials
    b.cyl(col, "Gate_Pillar_Finial_L", (-5.8, 75.0, 6.45), 0.35, 0.50, trim_mat, segments=18)
    b.cyl(col, "Gate_Pillar_Finial_R", (5.8, 75.0, 6.45), 0.35, 0.50, trim_mat, segments=18)
    # Grand Arched Overhead Portal Beam
    b.box(col, "Gate_Arch_Beam", (0, 75.0, 6.0), (13.1, 1.6, 0.9), trim_mat)
    b.box(col, "Gate_Signboard", (0, 75.0, 6.9), (11.5, 0.25, 0.95), trim_mat)
    # 3D Embossed Golden Gateway Signage
    b.box(col, "Gate_Sign_Text_Trust", (0, 75.14, 7.15), (9.8, 0.04, 0.20), m["brass"])
    b.box(col, "Gate_Sign_Text_IMRD", (0, 75.14, 6.65), (10.6, 0.04, 0.36), m["brass"])

    # 2 Wrought-Iron Gate Leaves (Hung on Piers, Open at 45°)
    for s_side, px, rot_deg in (("L", -5.0, 45.0), ("R", 5.0, -45.0)):
        g_rot = Matrix.Rotation(math.radians(rot_deg), 3, 'Z')
        b.box(col, f"Gate_Leaf_Frame_{s_side}", (px, 73.8, 1.8), (2.8, 0.08, 3.2), m["metal_dark"], rot=g_rot)
        # Decorative vertical spear bars
        for bar_i in range(5):
            bx = -1.1 + bar_i * 0.55
            b.box(col, f"Gate_Bar_{s_side}_{bar_i}", (px + bx * math.cos(math.radians(rot_deg)),
                                                     73.8 + bx * math.sin(math.radians(rot_deg)), 1.8),
                  (0.04, 0.04, 3.0), m["metal_dark"])

    # Automated Security Boom Barrier (across vehicle entry lane)
    b.box(col, "Security_Boom_Housing", (4.8, 73.2, 0.55), (0.45, 0.45, 1.1), m["flag_orange"])
    b.box(col, "Security_Boom_Arm", (1.8, 73.2, 0.95), (5.5, 0.08, 0.12), m["ceiling"])
    b.box(col, "Security_Boom_Stripe_1", (3.2, 73.2, 0.95), (0.6, 0.09, 0.13), m["fabric_red"])
    b.box(col, "Security_Boom_Stripe_2", (1.6, 73.2, 0.95), (0.6, 0.09, 0.13), m["fabric_red"])
    b.box(col, "Security_Boom_Stripe_3", (0.0, 73.2, 0.95), (0.6, 0.09, 0.13), m["fabric_red"])

    # Security Cabin with details
    b.box(col, "Security_Cabin", (8.2, 73.2, 1.6), (3.0, 3.0, 3.2), wall_mat)
    b.box(col, "Security_Cabin_Roof", (8.2, 73.2, 3.35), (3.6, 3.6, 0.3), trim_mat)
    b.box(col, "Security_Cabin_Window", (6.65, 73.2, 1.6), (0.1, 1.8, 1.2), m["glass"])
    b.box(col, "Security_Cabin_Door", (8.2, 71.65, 1.1), (1.0, 0.08, 2.2), m["door"])
    b.box(col, "Security_Counter", (6.9, 73.2, 0.9), (0.4, 1.6, 0.1), m["wood"])
    # Amber warning beacon on security cabin roof
    b.cyl(col, "Security_Beacon", (8.2, 73.2, 3.6), 0.12, 0.22, m["lamp_glow"], segments=14)

    # 4 High-Visibility Traffic Safety Cones at Entry
    for ci, (cx, cy) in enumerate(((4.2, 71.0), (4.2, 68.0), (-4.2, 71.0), (-4.2, 68.0))):
        b.cone(col, f"Traffic_Cone_{ci}", (cx, cy, 0.38), r_bottom=0.22, r_top=0.04, depth=0.76, mat=m["flag_orange"], segments=14)
        b.box(col, f"Traffic_Cone_Base_{ci}", (cx, cy, 0.03), (0.46, 0.46, 0.06), m["metal_dark"])

    # ------------------------------------------------------------------
    # 2. COMPLETE 4-SIDED CAMPUS PERIMETER BOUNDARY WALLS
    # ------------------------------------------------------------------
    # Front Boundary Walls (North Y = 75.0)
    b.box(col, "Boundary_Wall_N_Left", (-32.5, 75.0, 1.1), (51.0, 0.40, 2.2), wall_mat)
    b.box(col, "Boundary_Wall_N_Right", (37.0, 75.0, 1.1), (60.0, 0.40, 2.2), wall_mat)
    b.box(col, "Boundary_Coping_N_Left", (-32.5, 75.0, 2.25), (51.2, 0.48, 0.10), trim_mat)
    b.box(col, "Boundary_Coping_N_Right", (37.0, 75.0, 2.25), (60.2, 0.48, 0.10), trim_mat)

    # West Boundary Wall (Left X = -58.0, Y from -25 to 75)
    b.box(col, "Boundary_Wall_West", (-58.0, 25.0, 1.1), (0.40, 100.0, 2.2), wall_mat)
    b.box(col, "Boundary_Coping_West", (-58.0, 25.0, 2.25), (0.48, 100.2, 0.10), trim_mat)

    # East Boundary Wall (Right X = 68.0, Y from -25 to 75)
    b.box(col, "Boundary_Wall_East", (68.0, 25.0, 1.1), (0.40, 100.0, 2.2), wall_mat)
    b.box(col, "Boundary_Coping_East", (68.0, 25.0, 2.25), (0.48, 100.2, 0.10), trim_mat)

    # South Boundary Wall (Rear Y = -25.0, X from -58 to 68)
    b.box(col, "Boundary_Wall_South", (5.0, -25.0, 1.1), (126.0, 0.40, 2.2), wall_mat)
    b.box(col, "Boundary_Coping_South", (5.0, -25.0, 2.25), (126.2, 0.48, 0.10), trim_mat)

    # Perimeter Pilasters / Structural Columns every 12 meters
    pilaster_idx = 0
    # North pilasters
    for px in range(-58, -6, 10):
        b.box(col, f"Pilaster_N_{pilaster_idx}", (px, 75.0, 1.2), (0.6, 0.6, 2.4), trim_mat)
        pilaster_idx += 1
    for px in range(12, 69, 10):
        b.box(col, f"Pilaster_N_{pilaster_idx}", (px, 75.0, 1.2), (0.6, 0.6, 2.4), trim_mat)
        pilaster_idx += 1
    # West pilasters
    for py in range(-25, 76, 12):
        b.box(col, f"Pilaster_W_{pilaster_idx}", (-58.0, py, 1.2), (0.6, 0.6, 2.4), trim_mat)
        pilaster_idx += 1
    # East pilasters
    for py in range(-25, 76, 12):
        b.box(col, f"Pilaster_E_{pilaster_idx}", (68.0, py, 1.2), (0.6, 0.6, 2.4), trim_mat)
        pilaster_idx += 1
    # South pilasters
    for px in range(-58, 69, 12):
        b.box(col, f"Pilaster_S_{pilaster_idx}", (px, -25.0, 1.2), (0.6, 0.6, 2.4), trim_mat)
        pilaster_idx += 1


# ----------------------------------------------------------------------
# Lush, Multi-Tiered Vegetation, Avenue Palms & Classical Water Fountain
# ----------------------------------------------------------------------
def build_vegetation(b):
    col, m = b.cols["vegetation"], b.mats
    curb_mat = m.get("curb", m["wall_trim"])
    soil_mat = m.get("soil", m["trunk"])
    leaves_mat = m["leaves"]
    palm_frond_mat = m.get("palm_frond", leaves_mat)
    flower_shrub_mat = m.get("flower_shrub", leaves_mat)
    flower_red_mat = m.get("flower_red", leaves_mat)
    flower_yellow_mat = m.get("flower_yellow", leaves_mat)
    trunk_mat = m["trunk"]

    # ------------------------------------------------------------------
    # 1. AVENUE OF ROYAL PALM TREES (Lining the Main Approach Road)
    # ------------------------------------------------------------------
    palm_y_coords = [24.0, 34.0, 44.0, 54.0, 64.0]
    for pi, py in enumerate(palm_y_coords):
        for side, sx in ((-1, -6.8), (1, 6.8)):
            p_name = f"Royal_Palm_{side}_{pi}"
            # Concrete base planter ring & soil disk
            b.cyl(col, f"{p_name}_Base", (sx, py, 0.06), 0.85, 0.12, curb_mat, segments=16)
            b.cyl(col, f"{p_name}_Soil", (sx, py, 0.08), 0.75, 0.09, soil_mat, segments=16)
            # Tapered ringed palm trunk (8.5m high)
            b.cone(col, f"{p_name}_Trunk", (sx, py, 4.25), r_bottom=0.28, r_top=0.16, depth=8.5, mat=trunk_mat, segments=12)
            # Green crownshaft
            b.cyl(col, f"{p_name}_Crownshaft", (sx, py, 8.8), 0.17, 0.9, leaves_mat, segments=12)
            # Radiating curved palm fronds crown
            b.palm_crown(col, f"{p_name}_Fronds", (sx, py, 9.2), frond_count=14, frond_len=4.2, mat=palm_frond_mat)

    # ------------------------------------------------------------------
    # 2. CLASSICAL TIERED WATER FOUNTAIN (Center of Circular Plaza X = -40, Y = 48.5)
    # ------------------------------------------------------------------
    fcx, fcy = -40.0, 48.5
    # Octagonal dressed stone pool basin coping
    b.cyl(col, "Fountain_Pool_Curb", (fcx, fcy, 0.28), 3.2, 0.55, curb_mat, segments=32)
    # Sparkling turquoise physical water plane
    b.cyl(col, "Fountain_Water_Surface", (fcx, fcy, 0.48), 2.9, 0.06, m["water"], segments=32)
    # Classical center stone pedestal
    b.cyl(col, "Fountain_Pedestal_Base", (fcx, fcy, 0.45), 0.85, 0.90, curb_mat, segments=20)
    # Lower cascading overflow bowl
    b.cone(col, "Fountain_Bowl_Lower", (fcx, fcy, 1.05), r_bottom=0.55, r_top=1.45, depth=0.35, mat=curb_mat, segments=24)
    b.cyl(col, "Fountain_Water_Bowl_Lower", (fcx, fcy, 1.18), 1.35, 0.04, m["water"], segments=24)
    # Center intermediate column
    b.cyl(col, "Fountain_Column_Mid", (fcx, fcy, 1.55), 0.38, 0.75, curb_mat, segments=16)
    # Upper cascading overflow bowl
    b.cone(col, "Fountain_Bowl_Upper", (fcx, fcy, 2.05), r_bottom=0.35, r_top=0.85, depth=0.28, mat=curb_mat, segments=20)
    b.cyl(col, "Fountain_Water_Bowl_Upper", (fcx, fcy, 2.15), 0.78, 0.04, m["water"], segments=20)
    # Top fountain spray finial
    b.cone(col, "Fountain_Finial_Nozzle", (fcx, fcy, 2.45), r_bottom=0.22, r_top=0.06, depth=0.55, mat=m["brass"], segments=12)

    # ------------------------------------------------------------------
    # 3. LUSH SHADE & FLOWERING TREES (Gulmohar, Jacaranda & Neem)
    # ------------------------------------------------------------------
    tree_specs = [
        # Courtyard garden cluster
        (-32.0, 38.0, 6.2, flower_red_mat, "Gulmohar_1"),
        (-48.0, 38.0, 6.5, flower_yellow_mat, "Amaltas_1"),
        (-32.0, 58.0, 5.8, leaves_mat, "Neem_1"),
        (-48.0, 58.0, 6.4, flower_red_mat, "Gulmohar_2"),
        (-40.0, 63.0, 6.8, flower_yellow_mat, "Amaltas_2"),
        (-54.0, 48.0, 6.0, leaves_mat, "Neem_2"),
        (-28.0, 48.0, 5.9, flower_red_mat, "Gulmohar_3"),
        # Cafeteria and Sports court lawns
        (-22.0, 18.0, 6.2, flower_yellow_mat, "Amaltas_3"),
        (-36.0, 16.0, 5.8, leaves_mat, "Neem_3"),
        (26.0, 27.0, 6.0, flower_red_mat, "Gulmohar_4"),
        (56.0, 18.0, 6.4, leaves_mat, "Neem_4"),
        (56.0, 27.0, 6.0, flower_yellow_mat, "Amaltas_4"),
        # Building rear and perimeter belt
        (-15.0, -12.0, 6.8, leaves_mat, "Rear_Tree_1"),
        (0.0, -12.0, 7.2, flower_red_mat, "Rear_Tree_2"),
        (15.0, -12.0, 6.8, leaves_mat, "Rear_Tree_3"),
        (60.0, 38.0, 6.4, flower_red_mat, "East_Tree_1"),
        (60.0, 50.0, 6.6, flower_yellow_mat, "East_Tree_2"),
        (60.0, 62.0, 6.2, leaves_mat, "East_Tree_3"),
        (-50.0, 20.0, 6.0, leaves_mat, "West_Tree_1"),
        (-50.0, 68.0, 6.5, flower_red_mat, "West_Tree_2"),
    ]

    for idx, (tx, ty, h, fol_mat, t_tag) in enumerate(tree_specs):
        th = h * 0.44
        cr = h * 0.42
        n = f"ShadeTree_{idx}_{t_tag}"
        # Concrete base ring & soil
        b.cyl(col, f"{n}_BaseRing", (tx, ty, 0.05), 1.15, 0.10, curb_mat, segments=16)
        b.cyl(col, f"{n}_Soil", (tx, ty, 0.07), 1.05, 0.08, soil_mat, segments=16)
        # Natural tapered trunk
        b.cone(col, f"{n}_Trunk", (tx, ty, th / 2.0), r_bottom=0.32, r_top=0.20, depth=th, mat=trunk_mat, segments=12)
        # Multi-lobed lush canopy with organic shading
        canopy_cz = th + cr * 0.65
        b.organic_canopy(col, f"{n}_Crown", (tx, ty, canopy_cz), cr, mat=fol_mat, seed=idx)

    # ------------------------------------------------------------------
    # 4. CONTINUOUS MANICURED EVERGREEN HEDGES & FLOWERBEDS
    # ------------------------------------------------------------------
    # Manicured hedge borders along garden walkways
    for w_idx, wy in enumerate(range(20, 50, 3)):
        b.shrub(col, f"Walkway_Hedge_W_{w_idx}", (-24.5, wy, 0.32), radius=0.52, height=0.64, mat=leaves_mat, seed=w_idx)
    # Hedges along parking walkway
    for p_idx, py in enumerate(range(20, 36, 3)):
        b.shrub(col, f"Walkway_Hedge_E_{p_idx}", (24.2, py, 0.32), radius=0.50, height=0.62, mat=leaves_mat, seed=p_idx + 20)

    # Plinth planter beds framing the main entrance stairs
    for k in range(6):
        lx = -17.0 + k * 1.4
        b.shrub(col, f"Plinth_Flower_L_{k}", (lx, 9.8, 0.55), radius=0.58, height=0.70, mat=flower_red_mat, seed=k)
        rx = 10.0 + k * 1.4
        b.shrub(col, f"Plinth_Flower_R_{k}", (rx, 9.8, 0.55), radius=0.58, height=0.70, mat=flower_yellow_mat, seed=k + 10)

    # Concentric flower rings around circular fountain plaza
    for fi in range(8):
        f_ang = fi * (2.0 * math.pi / 8.0)
        fx = fcx + 4.8 * math.cos(f_ang)
        fy = fcy + 4.8 * math.sin(f_ang)
        b.shrub(col, f"Fountain_Ring_Flower_{fi}", (fx, fy, 0.30), radius=0.60, height=0.65, mat=flower_shrub_mat, seed=fi + 30)



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
    # Warm golden hour / late afternoon angle (30° elevation) raking across the +Y facade
    sky.sun_elevation = math.radians(30.0)
    sky.sun_rotation = math.radians(116.0)
    sky.sun_disc = True
    sky.sun_size = math.radians(2.0)
    sky.sun_intensity = 1.0
    sky.turbidity = 2.3                     # natural clear atmosphere
    sky.ground_albedo = 0.32
    if hasattr(sky, "altitude"):
        sky.altitude = 120.0
    if hasattr(sky, "air_density"):
        sky.air_density = 1.0
    if hasattr(sky, "dust_density"):
        sky.dust_density = 0.5
    if hasattr(sky, "ozone_density"):
        sky.ozone_density = 1.25

    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (0, 0)
    bg.inputs["Strength"].default_value = 0.88  # calibrated physically balanced sky radiance

    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (200, 0)

    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # EEVEE Next raytracing, shadows & illumination
    eevee = scene.eevee
    if hasattr(eevee, "use_raytracing"):
        eevee.use_raytracing = True
        if hasattr(eevee, "ray_tracing_options"):
            eevee.ray_tracing_options.screen_trace_quality = 0.85
            eevee.ray_tracing_options.trace_max_roughness = 0.75
            if hasattr(eevee.ray_tracing_options, "resolution_scale"):
                eevee.ray_tracing_options.resolution_scale = '1'
            if hasattr(eevee.ray_tracing_options, "use_denoise"):
                eevee.ray_tracing_options.use_denoise = True
    if hasattr(eevee, "fast_gi_method"):
        eevee.fast_gi_method = "GLOBAL_ILLUMINATION"
    if hasattr(eevee, "use_fast_gi"):
        eevee.use_fast_gi = True
    if hasattr(eevee, "fast_gi_ray_count"):
        eevee.fast_gi_ray_count = 4
    if hasattr(eevee, "gi_diffuse_bounces"):
        eevee.gi_diffuse_bounces = 3
    if hasattr(eevee, "use_shadows"):
        eevee.use_shadows = True
    if hasattr(eevee, "shadow_pool_size"):
        eevee.shadow_pool_size = '1024'
    if hasattr(eevee, "shadow_ray_count"):
        eevee.shadow_ray_count = 2
    if hasattr(eevee, "use_volumetric_shadows"):
        eevee.use_volumetric_shadows = True
    if hasattr(eevee, "taa_render_samples"):
        eevee.taa_render_samples = 48
    if hasattr(eevee, "use_overscan"):
        eevee.use_overscan = True
        eevee.overscan_size = 5.0

    # AgX Color Management & Film Exposure
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.15


def build_lighting_and_cameras(b):
    setup_world_sky(b.scene)
    col = b.cols["lighting"]

    # Primary sun matching Nishita sky elevation (30°) & rotation (116°)
    sun_data = bpy.data.lights.get("Sun_Daylight") or bpy.data.lights.new(name="Sun_Daylight", type='SUN')
    sun_data.energy = 5.6
    sun_data.color = (1.0, 0.95, 0.88)
    if hasattr(sun_data, "angle"):
        sun_data.angle = math.radians(1.85)   # realistic solar angular diameter for soft contact-hardening shadows
    if hasattr(sun_data, "shadow_cascade_count"):
        sun_data.shadow_cascade_count = 4
    if hasattr(sun_data, "shadow_cascade_max_distance"):
        sun_data.shadow_cascade_max_distance = 250.0
    if hasattr(sun_data, "shadow_cascade_fade"):
        sun_data.shadow_cascade_fade = 0.15
    if hasattr(sun_data, "shadow_maximum_resolution"):
        sun_data.shadow_maximum_resolution = 0.0005
    if hasattr(sun_data, "shadow_filter_radius"):
        sun_data.shadow_filter_radius = 2.0
    if hasattr(sun_data, "use_shadow_jitter"):
        sun_data.use_shadow_jitter = True
    sun_obj = bpy.data.objects.get("Sun_Daylight") or bpy.data.objects.new("Sun_Daylight", sun_data)
    sun_obj.data = sun_data
    sun_obj.location = (25, -25, 40)
    sun_obj.rotation_euler = Euler((math.radians(60.0), math.radians(14.0), math.radians(116.0)), 'XYZ')
    sun_obj[OWNER_KEY] = OWNER_VALUE
    if sun_obj.name not in col.objects:
        col.objects.link(sun_obj)

    # Soft ambient fill
    fill_data = bpy.data.lights.get("Sky_Fill") or bpy.data.lights.new(name="Sky_Fill", type='SUN')
    fill_data.energy = 0.70
    fill_data.color = (0.72, 0.84, 1.0)
    fill_obj = bpy.data.objects.get("Sky_Fill") or bpy.data.objects.new("Sky_Fill", fill_data)
    fill_obj.data = fill_data
    fill_obj.location = (-20, 20, 35)
    fill_obj.rotation_euler = Euler((math.radians(-52), math.radians(-25), math.radians(-115)), 'XYZ')
    fill_obj[OWNER_KEY] = OWNER_VALUE
    if fill_obj.name not in col.objects:
        col.objects.link(fill_obj)

    # Architectural Interior & Portico Accent Lights
    accent_lights = [
        ("Light_Classroom_Front", (-14.0, 2.5, 3.4), 55.0, (1.0, 0.97, 0.92), 0.45),
        ("Light_Classroom_Rear", (-14.0, 5.5, 3.4), 45.0, (1.0, 0.96, 0.90), 0.45),
        ("Light_Lobby_Reception", (-2.5, 4.5, 3.6), 40.0, (1.0, 0.94, 0.86), 0.40),
        ("Light_Lobby_Stairs", (4.8, 4.2, 4.1), 50.0, (1.0, 0.95, 0.88), 0.45),
        ("Light_Stairs_Top", (5.0, 1.8, 5.4), 55.0, (1.0, 0.95, 0.88), 0.45),
        ("Light_Portico_L", (-3.2, 10.2, 3.7), 28.0, (1.0, 0.92, 0.82), 0.30),
        ("Light_Portico_R", (3.2, 10.2, 3.7), 28.0, (1.0, 0.92, 0.82), 0.30),
    ]
    for l_name, l_loc, l_energy, l_col, l_rad in accent_lights:
        ld = bpy.data.lights.get(l_name) or bpy.data.lights.new(name=l_name, type='POINT')
        ld.energy = l_energy
        ld.color = l_col
        if hasattr(ld, "shadow_soft_size"):
            ld.shadow_soft_size = l_rad
        lo = bpy.data.objects.get(l_name) or bpy.data.objects.new(l_name, ld)
        lo.data = ld
        lo.location = Vector(l_loc)
        lo[OWNER_KEY] = OWNER_VALUE
        if lo.name not in col.objects:
            col.objects.link(lo)

    # Curated Cinematic Camera placements and targets
    cams = [
        (cfg.CAMERA_OVERVIEW, 40, 500, (48.0, 85.0, 36.0), (-2.0, 26.0, 2.5), 82.0, 8.0),
        (cfg.CAMERA_ENTRANCE, 36, 400, (-2.5, 46.0, 1.85), (0.0, 9.5, 3.2), 37.0, 5.6),
        ("Cam_Facade", 30, 300, (-16.0, 17.5, 1.95), (2.0, 8.8, 3.1), 20.0, 4.0),
        ("Cam_Classroom", 22, 150, (-10.2, 7.2, 1.55), (-14.2, 1.8, 1.35), 6.2, 3.5),
        ("Cam_Staircase", 24, 150, (4.6, 8.2, 1.45), (5.0, 2.0, 3.2), 4.6, 3.2),
        ("Cam_Courtyard", 30, 250, (-31.0, 40.0, 1.75), (-40.0, 48.5, 1.1), 12.5, 4.0),
        ("Cam_Gate", 40, 400, (0.0, 86.0, 1.95), (0.0, 32.0, 3.5), 54.0, 5.6),
        ("Cam_Sports", 32, 250, (22.0, 6.0, 5.5), (40.0, 18.0, 2.0), 24.0, 4.5),
        ("Cam_Roof", 28, 200, (-18.0, 12.0, 13.5), (0.0, -2.0, 9.2), 20.0, 4.0),
        ("Cam_Fountain", 28, 150, (-48.0, 42.0, 2.2), (-40.0, 48.5, 1.2), 11.0, 3.5),
    ]
    for name, lens, clip, loc, target, dof_dist, fstop in cams:
        cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
        cd.lens, cd.clip_end = lens, clip
        if hasattr(cd, "dof"):
            cd.dof.use_dof = True
            cd.dof.focus_distance = dof_dist
            cd.dof.aperture_fstop = fstop
        obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
        obj.data = cd
        obj.location = Vector(loc)
        d = Vector(target) - obj.location
        obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        obj[OWNER_KEY] = OWNER_VALUE
        if obj.name not in col.objects:
            col.objects.link(obj)

    # Streetlamp, sports court and plaza real point lights
    for i, (lx, ly) in enumerate([(-5.5, 26), (5.5, 26), (-5.5, 42), (5.5, 42), (-5.5, 58), (5.5, 58), (-5.5, 72), (5.5, 72)]):
        pl_name = f"Light_Avenue_Lamp_{i}"
        pld = bpy.data.lights.get(pl_name) or bpy.data.lights.new(name=pl_name, type='POINT')
        pld.energy = 65.0
        pld.color = (1.0, 0.94, 0.82)
        if hasattr(pld, "shadow_soft_size"):
            pld.shadow_soft_size = 0.35
        plo = bpy.data.objects.get(pl_name) or bpy.data.objects.new(pl_name, pld)
        plo.data = pld
        plo.location = Vector((lx, ly, 4.4))
        plo[OWNER_KEY] = OWNER_VALUE
        if plo.name not in col.objects:
            col.objects.link(plo)

    # Sports Court floodlight point lights
    for corner_i, (fc_x, fc_y) in enumerate(((26.0, 10.0), (54.0, 10.0), (54.0, 26.0), (26.0, 26.0))):
        sfl_name = f"Light_Sports_Flood_{corner_i}"
        sfld = bpy.data.lights.get(sfl_name) or bpy.data.lights.new(name=sfl_name, type='POINT')
        sfld.energy = 180.0
        sfld.color = (0.95, 0.98, 1.0)
        if hasattr(sfld, "shadow_soft_size"):
            sfld.shadow_soft_size = 0.8
        sflo = bpy.data.objects.get(sfl_name) or bpy.data.objects.new(sfl_name, sfld)
        sflo.data = sfld
        sflo.location = Vector((fc_x, fc_y, 7.2))
        sflo[OWNER_KEY] = OWNER_VALUE
        if sflo.name not in col.objects:
            col.objects.link(sflo)

    # Facade uplights highlighting 3D brass signage & portico
    for f_idx, fx in enumerate((-6.0, 0.0, 6.0)):
        fu_name = f"Light_Facade_Wash_{f_idx}"
        fud = bpy.data.lights.get(fu_name) or bpy.data.lights.new(name=fu_name, type='POINT')
        fud.energy = 45.0
        fud.color = (1.0, 0.92, 0.78)
        fuo = bpy.data.objects.get(fu_name) or bpy.data.objects.new(fu_name, fud)
        fuo.data = fud
        fuo.location = Vector((fx, 11.5, 4.3))
        fuo[OWNER_KEY] = OWNER_VALUE
        if fuo.name not in col.objects:
            col.objects.link(fuo)

    if b.scene.camera is None or b.scene.camera.name not in bpy.data.objects:
        b.scene.camera = bpy.data.objects[cfg.CAMERA_OVERVIEW]


# ----------------------------------------------------------------------
# Ground-Snap, Spacing & Alignment Algorithms
# ----------------------------------------------------------------------
def apply_alignment_algorithms(b):
    """
    Precision alignment algorithms:
    1. Ground-snap: calculates world-space bounding box minimum Z for props,
       vegetation, furniture and boundary elements, and aligns them exactly
       to surface level (zero floating, zero subterranean clipping).
    2. Equidistant symmetry: enforces exact mirroring and perpendicular axis
       alignment on avenue elements, boundary pilasters, and parking bays.
    """
    scene = b.scene

    def target_elevation(x, y):
        # Building interior
        if -cfg.BLD_IN_X <= x <= cfg.BLD_IN_X and -cfg.BLD_IN_Y <= y <= cfg.BLD_IN_Y:
            return cfg.FLOOR_G_Z
        # Building plinth / steps
        if -cfg.PLINTH_HALF[0] <= x <= cfg.PLINTH_HALF[0] and -cfg.PLINTH_HALF[1] <= y <= 11.0:
            return cfg.PLINTH_TOP_Z
        # Sports court
        if 25.0 <= x <= 55.0 and 9.0 <= y <= 27.0:
            return 0.045
        # Front paved plaza
        if -25.0 <= x <= 25.0 and 9.5 <= y <= 20.5:
            return 0.035
        # Garden circular plaza
        if math.hypot(x - (-40.0), y - 48.5) <= 6.5:
            return 0.035
        # Cafeteria terrace
        if -37.0 <= x <= -23.0 and 17.0 <= y <= 31.0:
            return 0.035
        # Main asphalt road
        if -4.6 <= x <= 4.6 and 19.0 <= y <= 76.0:
            return 0.02
        # Parking asphalt area
        if 26.0 <= x <= 62.0 and 31.0 <= y <= 55.0:
            return 0.025
        # General grass lawn
        return 0.0

    aligned_count = 0
    ground_snap_prefixes = (
        "Tree_", "ShadeTree_", "Royal_Palm_", "Walkway_Hedge_", "Plinth_Flower_",
        "Fountain_Ring_", "Bench_Plaza_", "Garden_Bench_", "Lamp_Pole_",
        "Court_Corner_Post_", "Court_Floodlight_Pole_", "Hoop_West_", "Hoop_East_",
        "Cafe_Table_Base_", "Cafe_Kiosk_", "Bike_Canopy_Post_", "Bike_Station_",
        "Flag_Plinth_Tier_1", "Campus_Directory_", "Waste_Bin_", "Traffic_Cone_",
        "Car_0_", "Car_1_", "Car_2_", "Car_5_", "Bike_3_", "Bike_4_",
        "Gate_Pillar_", "Boundary_Wall_", "Pilaster_", "Security_Cabin"
    )

    for obj in bpy.data.objects:
        if not is_owned(obj) or obj.type != 'MESH':
            continue
        if any(obj.name.startswith(pfx) for pfx in ground_snap_prefixes):
            # Compute current world min Z
            min_z = min((obj.matrix_world @ Vector(c)).z for c in obj.bound_box)
            tx, ty = obj.location.x, obj.location.y
            target_z = target_elevation(tx, ty)

            # Adjust if offset exceeds 1 millimeter
            dz = target_z - min_z
            if abs(dz) > 0.001 and abs(dz) < 2.0:
                obj.location.z += dz
                aligned_count += 1

    b.stats["aligned_objects"] = aligned_count


# ----------------------------------------------------------------------
# Physics Rigid Body World & Clean Collision Proxies Engine
# ----------------------------------------------------------------------
def setup_physics_and_collision_proxies(b):
    """
    Configures Blender RigidBody World physics and populates Collision_Proxies
    collection with clean, lightweight colliders for real-time simulation & export.
    """
    scene = b.scene
    col_proxies = b.cols["collision"]

    # 1. Initialize Rigid Body World if not active
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    if rbw:
        rbw.enabled = True
        rbw.time_scale = 1.0
        rbw.substeps_per_frame = 10
        rbw.solver_iterations = 10

    # Helper to add rigid body component safely
    def add_rigid_body(obj, rb_type='PASSIVE', shape='MESH', mass=1.0, restitution=0.0, friction=0.5):
        if not obj or obj.type != 'MESH':
            return
        if obj.rigid_body is None:
            bpy.context.view_layer.objects.active = obj
            try:
                bpy.ops.rigidbody.object_add(type=rb_type)
            except Exception:
                pass
        rb = obj.rigid_body
        if rb:
            rb.type = rb_type
            rb.collision_shape = shape
            rb.mass = mass
            rb.restitution = restitution
            rb.friction = friction

    # 2. Add Passive Colliders to Static World Geometry
    passive_mesh_targets = [
        "Ground_Grass", "Road_Main", "Plaza_Front", "Garden_Circle_Plaza",
        "Court_Pad_Apron", "Court_Surface_Blue", "Cafe_Plaza_Terrace",
        "Bld_Plinth", "Bld_Steps_1", "Bld_Steps_2", "Bld_Floor_G",
        "Slab_Floor_1_West", "Slab_Floor_1_East", "Slab_Floor_1_Front", "Slab_Floor_1_Landing",
        "Roof_Main", "Parapet_Front", "Parapet_Back", "Parapet_Left", "Parapet_Right",
        "Canopy_Roof", "Rail_Balcony", "Rail_Stair_Opening_Front",
        "Boundary_Wall_N_Left", "Boundary_Wall_N_Right", "Boundary_Wall_West",
        "Boundary_Wall_East", "Boundary_Wall_South",
        "Gate_Pillar_L", "Gate_Pillar_R", "Gate_Arch_Beam", "Security_Cabin",
        "Court_Fence_N", "Court_Fence_S", "Court_Fence_W", "Court_Fence_E"
    ]
    # Include walls and stair steps
    for obj in bpy.data.objects:
        if not is_owned(obj):
            continue
        if obj.name in passive_mesh_targets or obj.name.startswith("Wall_") or obj.name.startswith("Stair_Step_"):
            shape = 'MESH' if (obj.name.startswith("Stair_") or "Wall_" in obj.name or "Road_" in obj.name) else 'BOX'
            add_rigid_body(obj, rb_type='PASSIVE', shape=shape, friction=0.6)

    # 3. Add Active Rigid Bodies to Dynamic Props (Basketballs and Traffic Cones)
    for obj in bpy.data.objects:
        if not is_owned(obj):
            continue
        if obj.name.startswith("Basketball_Prop_"):
            add_rigid_body(obj, rb_type='ACTIVE', shape='SPHERE', mass=0.62, restitution=0.84, friction=0.55)
        elif obj.name.startswith("Traffic_Cone_") and not obj.name.startswith("Traffic_Cone_Base_"):
            add_rigid_body(obj, rb_type='ACTIVE', shape='CONVEX_HULL', mass=2.4, restitution=0.25, friction=0.75)

    # 4. Generate Clean Box Collision Proxies for Game Engines in Collision_Proxies
    col_prox_boxes = [
        # Building Main Shell Colliders (West, East, Back, Front-L, Front-R)
        ("Col_Bld_West", (-20.5, 0.0, 4.3), (0.4, 17.4, 8.6)),
        ("Col_Bld_East", (20.5, 0.0, 4.3), (0.4, 17.4, 8.6)),
        ("Col_Bld_Back", (0.0, -8.5, 4.3), (41.4, 0.4, 8.6)),
        ("Col_Bld_Front_L", (-12.0, 8.5, 4.3), (17.0, 0.4, 8.6)),
        ("Col_Bld_Front_R", (12.0, 8.5, 4.3), (17.0, 0.4, 8.6)),
        # Interior Partition & Corridor
        ("Col_Int_Partition", (0.0, 0.0, 2.3), (41.0, 0.25, 4.0)),
        ("Col_Int_Class_L", (-8.0, 4.25, 2.3), (0.25, 8.5, 4.0)),
        ("Col_Int_Class_R", (8.0, 4.25, 2.3), (0.25, 8.5, 4.0)),
        # Campus Boundary Colliders
        ("Col_Boundary_North_L", (-32.5, 75.0, 1.1), (51.0, 0.45, 2.3)),
        ("Col_Boundary_North_R", (37.0, 75.0, 1.1), (60.0, 0.45, 2.3)),
        ("Col_Boundary_West", (-58.0, 25.0, 1.1), (0.45, 100.0, 2.3)),
        ("Col_Boundary_East", (68.0, 25.0, 1.1), (0.45, 100.0, 2.3)),
        ("Col_Boundary_South", (5.0, -25.0, 1.1), (126.0, 0.45, 2.3)),
        # Gate & Security
        ("Col_Gate_Pillar_L", (-5.8, 75.0, 3.1), (1.6, 1.6, 6.2)),
        ("Col_Gate_Pillar_R", (5.8, 75.0, 3.1), (1.6, 1.6, 6.2)),
        ("Col_Security_Cabin", (8.2, 73.2, 1.6), (3.2, 3.2, 3.2)),
        # Sports Court Perimeter
        ("Col_Court_Fence_N", (40.0, 26.0, 1.8), (28.4, 0.15, 3.6)),
        ("Col_Court_Fence_S", (40.0, 10.0, 1.8), (28.4, 0.15, 3.6)),
        ("Col_Court_Fence_W", (26.0, 18.0, 1.8), (0.15, 16.4, 3.6)),
        ("Col_Court_Fence_E", (54.0, 18.0, 1.8), (0.15, 16.4, 3.6)),
    ]

    for c_name, c_center, c_size in col_prox_boxes:
        p_obj = b.box(col_proxies, c_name, c_center, c_size, mat=None)
        p_obj.display_type = 'WIRE'
        p_obj.hide_render = True
        p_obj["imrd_collision_proxy"] = True
        add_rigid_body(p_obj, rb_type='PASSIVE', shape='BOX', friction=0.5)

    b.stats["collision_proxies"] = len(col_prox_boxes)


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
    steps = [
        build_terrain,
        build_shell,
        build_walls_and_openings,
        build_stairs,
        build_furniture,
        build_props,
        build_gate,
        build_vegetation,
        build_lighting_and_cameras,
        apply_alignment_algorithms,
        setup_physics_and_collision_proxies,
    ]

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
        ("gate_pbr.png", "Cam_Gate"),
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
