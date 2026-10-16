"""
test_geometry.py - Phase 2 geometry validation (run inside Blender, background OK).

    blender --background output/imrd_campus.blend --python tests/test_geometry.py

Validates the SAVED scene (mesh inspection, ray casts, BVH overlaps), then
rebuilds in-session to prove idempotency. Exit code 0 = all pass, 1 = failures.
Interactive controller/HUD behaviour is NOT covered here.
"""
import sys
import math
import importlib
import tempfile
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
cfg = importlib.import_module("game_config")
builder = importlib.import_module("01_build_campus")

results = []


def check(name, cond, detail=""):
    results.append((bool(cond), name, detail))
    print(("  PASS " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def obj(name):
    return bpy.data.objects.get(name)


def ray_obj(o, origin, direction, dist):
    inv = o.matrix_world.inverted()
    lo = inv @ Vector(origin)
    ld = (inv.to_3x3() @ Vector(direction)).normalized()
    hit, loc, nrm, idx = o.ray_cast(lo, ld, distance=dist)
    return hit, (o.matrix_world @ loc if hit else None)


def scene_ray(origin, direction, dist=50.0):
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, nrm, idx, o, mw = bpy.context.scene.ray_cast(dg, Vector(origin), Vector(direction), distance=dist)
    return (loc, o) if hit else (None, None)


def P(axis, fixed, along, off, z):
    return builder.P(axis, fixed, along, off, z)


# ----------------------------------------------------------------------
def test_collections_and_objects():
    print("[collections / objects]")
    for key, name in cfg.COLLECTIONS.items():
        check(f"collection {name}", name in bpy.data.collections)
    for name in cfg.STABLE_OBJECT_NAMES:
        check(f"stable object {name}", obj(name) is not None)
    for n in ("Bld_Plinth", "Bld_Floor_G", "Roof_Main", "Slab_Floor_1_West", "Slab_Floor_1_East",
              "Slab_Floor_1_Front", "Slab_Floor_1_Landing", "Wall_G_Front", "Wall_1_Front",
              "Stair_Step_01", f"Stair_Step_{cfg.STAIR_TREAD_COUNT:02d}", "Rail_Stair_L", "Rail_Stair_R"):
        check(f"object {n}", obj(n) is not None)
    owned = [o for o in bpy.data.objects if o.get(cfg.OWNER_KEY) == cfg.OWNER_VALUE]
    check("owned objects present", len(owned) > 300, str(len(owned)))
    bad = [o.name for o in owned if o.type == 'MESH' and (not o.data.polygons or o.dimensions.length < 1e-4)]
    check("no empty/degenerate meshes", not bad, str(bad[:5]))
    nomat = [o.name for o in owned if o.type == 'MESH' and not o.data.materials]
    check("meshes have materials", not nomat, str(nomat[:5]))
    ids = [o.get("imrd_door_id") + o.name for o in owned if o.get("imrd_door_id")]
    check("unique door objects", len(ids) == len(set(ids)))
    opening_ids = [op["id"] for op in cfg.OPENINGS]
    check("unique opening ids", len(opening_ids) == len(set(opening_ids)))
    names = [o.name for o in bpy.data.objects]
    check("no .001 suffix names", not [n for n in names if n[-4:-3] == "." and n[-3:].isdigit()])


def test_wall_meshes_and_openings():
    print("[wall openings]")
    for key, w in cfg.WALLS.items():
        o = obj(w["name"])
        check(f"wall {w['name']} exists", o is not None)
        if o is None:
            continue
        bad, vol, nf = builder.mesh_health(o)
        check(f"{w['name']} manifold/outward", bad == 0 and vol > 0, f"nonmanifold={bad} vol={vol:.2f}")
        wz0, wz1 = w["z"]
        for op in [p for p in cfg.OPENINGS if p["wall"] == key]:
            zmid = (op["z0"] + op["z1"]) / 2
            axis, fixed = w["axis"], w["fixed"]
            d = (0, 1, 0) if axis == "X" else (1, 0, 0)
            # several rays through the opening: centre and near edges
            pts = [(op["along"], zmid), (op["along"] - op["width"] / 2 + 0.1, zmid),
                   (op["along"] + op["width"] / 2 - 0.1, zmid),
                   (op["along"], op["z0"] + 0.1), (op["along"], op["z1"] - 0.1)]
            hits = [ray_obj(o, P(axis, fixed, a, -1.0, z), d, 2.0)[0] for a, z in pts]
            check(f"opening {op['id']} is through-cut", not any(hits))
            # solid just above the head (lintel) must exist
            if op["z1"] + 0.1 < wz1 - 0.02:
                h, _ = ray_obj(o, P(axis, fixed, op["along"], -1.0, op["z1"] + 0.1), d, 2.0)
                check(f"opening {op['id']} has lintel", h)
            # solid beside the opening
            a_side = op["along"] + op["width"] / 2 + 0.15
            if a_side < w["a1"] - 0.05 and not any(abs(a_side - p["along"]) < p["width"] / 2 + 0.05
                                                   for p in cfg.OPENINGS if p["wall"] == key and p is not op):
                h, _ = ray_obj(o, P(axis, fixed, a_side, -1.0, zmid), d, 2.0)
                check(f"opening {op['id']} has jamb wall", h)
            if op["kind"] == "WINDOW" and op["z0"] - 0.1 > wz0 + 0.05:
                h, _ = ray_obj(o, P(axis, fixed, op["along"], -1.0, op["z0"] - 0.1), d, 2.0)
                check(f"opening {op['id']} has sill wall", h)
            if op["kind"] == "WINDOW":
                g = obj(f"Glass_{op['name']}")
                check(f"glass {op['name']} inset in opening",
                      g is not None and abs(g.dimensions[1 if axis == 'X' else 0] - cfg.WINDOW_GLASS_T) < 1e-4
                      and g.dimensions[0 if axis == 'X' else 1] < op["width"])
            check(f"frame {op['name']}", obj(f"Frame_{op['name']}") is not None)


def bvh_of(o):
    dg = bpy.context.evaluated_depsgraph_get()
    return BVHTree.FromObject(o, dg)


def world_bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def bbox_overlap(a, b, pad=0.0):
    return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))


def leaf_samples(leaf, step=0.04):
    """World-space points on both faces and mid-plane of a thin box leaf (4 cm grid + edges)."""
    lo = Vector(leaf.bound_box[0])
    hi = Vector(leaf.bound_box[6])
    dims = [hi[i] - lo[i] for i in range(3)]
    thin = dims.index(min(dims))
    big = [i for i in range(3) if i != thin]

    def ticks(a, b):
        n = max(2, int((b - a) / step) + 1)
        return [a + (b - a) * k / n for k in range(n + 1)]

    pts = []
    for t in (lo[thin], (lo[thin] + hi[thin]) / 2, hi[thin]):
        for u in ticks(lo[big[0]], hi[big[0]]):
            for v in ticks(lo[big[1]], hi[big[1]]):
                p = Vector((0, 0, 0))
                p[thin], p[big[0]], p[big[1]] = t, u, v
                pts.append(leaf.matrix_world @ p)
    return pts


def any_point_inside(other, pts, tol=1e-4):
    """True if any sample lies strictly inside the closed mesh `other` (penetration > tol)."""
    inv = other.matrix_world.inverted()
    for p in pts:
        lp = inv @ p
        ok, loc, nrm, idx = other.closest_point_on_mesh(lp)
        if ok and (lp - loc).dot(nrm) < -tol:
            return True
    return False


def test_doors():
    print("[doors]")
    scene_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.get(cfg.OWNER_KEY)
                  and not o.get("imrd_door_id")
                  and o.name.split("_")[0] in ("Wall", "Frame", "Glass", "Slab", "Stair", "Rail", "Bld",
                                               "Desk", "Bench", "Teacher", "Class", "Reception", "Canopy",
                                               "Column")]
    for op in [p for p in cfg.OPENINGS if p["kind"] in ("DOOR", "ENTRANCE")]:
        w = cfg.WALLS[op["wall"]]
        clear_w = op["width"] - 2 * op["frame_w"]
        clear_h = op["z1"] - op["z0"] - op["frame_w"]
        names = [op["door_name"]] if op["kind"] == "DOOR" else [cfg.ENTRANCE_DOOR_NAME, cfg.ENTRANCE_DOOR_B_NAME]
        leaves = [obj(n) for n in names]
        check(f"door objects exist {op['id']}", all(leaves))
        if not all(leaves):
            continue
        tot_w = sum(o["imrd_leaf_size"][0] for o in leaves)
        check(f"{op['id']} leaf width fits", tot_w < clear_w, f"{tot_w:.3f} vs {clear_w:.3f}")
        check(f"{op['id']} leaf height fits", leaves[0]["imrd_leaf_size"][2] < clear_h)
        check(f"{op['id']} leaf thinner than wall", leaves[0]["imrd_leaf_size"][1] < w["thick"])
        for leaf in leaves:
            hinge = Vector(leaf["imrd_hinge"])
            check(f"{leaf.name} origin at hinge", (leaf.location - hinge).length < 1e-5)
            lmin = Vector(leaf.bound_box[0])
            lmax = Vector(leaf.bound_box[6])
            ai = 0 if w["axis"] == "X" else 1
            check(f"{leaf.name} mesh starts at hinge edge",
                  min(abs(lmin[ai]), abs(lmax[ai])) < 1e-5, f"{lmin[ai]:.4f},{lmax[ai]:.4f}")
            check(f"{leaf.name} has id", leaf["imrd_door_id"] == op["id"])
            # collision-free in closed and open poses
            for label, deg in (("closed", 0.0), ("open", leaf["imrd_open_rot_z_deg"])):
                leaf.rotation_euler = Euler((0, 0, math.radians(deg)), 'XYZ')
                bpy.context.view_layer.update()
                hinge_after = leaf.matrix_world.translation
                check(f"{leaf.name} hinge fixed when {label}", (hinge_after - hinge).length < 1e-6)
                bb = world_bbox(leaf)
                hit = []
                pts = leaf_samples(leaf)
                for other in scene_objs:
                    if bbox_overlap(bb, world_bbox(other), 0.0) and any_point_inside(other, pts):
                        hit.append(other.name)
                check(f"{leaf.name} {label}: no intersections", not hit, str(hit[:4]))
            leaf.rotation_euler = Euler((0, 0, 0), 'XYZ')
    bpy.context.view_layer.update()


def test_stairs():
    print("[stairs / floors]")
    R, T = cfg.STAIR_RISER_H, cfg.STAIR_TREAD_D
    check("riser height 0.15-0.19", 0.15 <= R <= 0.19, f"{R:.3f}")
    check("tread depth >= 0.25", T >= 0.25)
    check("rise equals floor delta", abs(R * cfg.STAIR_RISER_COUNT - (cfg.FLOOR_1_Z - cfg.FLOOR_G_Z)) < 1e-9)
    prev = cfg.FLOOR_G_Z
    ok = True
    top_zs = []
    for i in range(1, cfg.STAIR_TREAD_COUNT + 1):
        yc = cfg.STAIR_Y_START - (i - 1) * T - T / 2
        loc, o = scene_ray((cfg.STAIR_X, yc, cfg.FLOOR_1_Z + 3.0), (0, 0, -1), 20)
        # first surface hit from above passes through the slab opening
        if loc is None or abs(loc.z - (cfg.FLOOR_G_Z + i * R)) > 1e-4 or abs((loc.z - prev) - R) > 1e-4:
            ok = False
        prev = loc.z if loc else prev
        top_zs.append(loc.z if loc else None)
    check("each tread top = floor + i*riser (ray cast from above)", ok)
    check("last riser reaches upper floor", abs((cfg.FLOOR_1_Z - top_zs[-1]) - R) < 1e-4)
    yl = (cfg.TOP_LANDING_Y[0] + cfg.TOP_LANDING_Y[1]) / 2
    loc, o = scene_ray((cfg.STAIR_X, yl, cfg.FLOOR_1_Z + 3.0), (0, 0, -1), 20)
    check("top landing surface at first-floor elevation", loc and abs(loc.z - cfg.FLOOR_1_Z) < 1e-4 and "Landing" in o.name,
          f"{loc} {o.name if o else None}")
    yb = (cfg.BOTTOM_LANDING_Y[0] + cfg.BOTTOM_LANDING_Y[1]) / 2
    loc, o = scene_ray((cfg.STAIR_X, yb, cfg.FLOOR_G_Z + 3.0), (0, 0, -1), 20)
    check("bottom landing at ground-floor elevation", loc and abs(loc.z - cfg.FLOOR_G_Z) < 1e-4, str(loc))
    # slab: opening free, surrounding slab present
    ox0, ox1 = cfg.STAIR_OPEN_X
    oy0, oy1 = cfg.STAIR_OPEN_Y
    for x, y in ((ox0 + 0.05, oy0 + 0.05), (ox1 - 0.05, oy1 - 0.05), (cfg.STAIR_X, (oy0 + oy1) / 2)):
        loc, o = scene_ray((x, y, cfg.FLOOR_1_Z - 0.05 - 0.25), (0, 0, 1), 2.0)
        check(f"slab opening clear at ({x:.2f},{y:.2f})", loc is None or "Slab" not in o.name, o.name if o else "")
    for x, y in ((ox0 - 0.3, 4.0), (ox1 + 0.3, 4.0), (cfg.STAIR_X, oy1 + 0.3), (cfg.STAIR_X, oy0 - 0.3)):
        loc, o = scene_ray((x, y, cfg.FLOOR_1_Z + 1.0), (0, 0, -1), 5.0)
        check(f"slab present around opening ({x:.1f},{y:.1f})", loc is not None and abs(loc.z - cfg.FLOOR_1_Z) < 1e-4)
    # headroom over every tread, at centre and both sides
    worst = 9.9
    for i in range(1, cfg.STAIR_TREAD_COUNT + 1):
        yc = cfg.STAIR_Y_START - (i - 1) * T - T / 2
        for dx in (-0.6, 0.0, 0.6):
            z = cfg.FLOOR_G_Z + i * R + 0.01
            loc, o = scene_ray((cfg.STAIR_X + dx, yc, z), (0, 0, 1), cfg.HEADROOM + 1.0)
            if loc is not None:
                worst = min(worst, loc.z - (z - 0.01))
    check(f"headroom >= {cfg.HEADROOM} m over all treads", worst >= cfg.HEADROOM, f"min={worst:.2f}")
    # no stair part inside any wall
    stair_objs = [o for o in bpy.data.objects if o.name.startswith(("Stair_Step", "Rail_Stair"))]
    walls = [o for o in bpy.data.objects if o.name.startswith("Wall_") or o.name.startswith("Frame_")]
    hits = []
    for s in stair_objs:
        sb = world_bbox(s)
        for wl in walls:
            if bbox_overlap(sb, world_bbox(wl)) and bvh_of(s).overlap(bvh_of(wl)):
                hits.append((s.name, wl.name))
    check("stairs/rails do not intersect walls or frames", not hits, str(hits[:3]))
    # corridor connection: arch on upper partition at stair x lets a ray cross
    arch = [p for p in cfg.OPENINGS if p["id"] == "arch_1_stair_landing"][0]
    wl = obj(cfg.WALLS[arch["wall"]]["name"])
    h, _ = ray_obj(wl, (cfg.STAIR_X, -1.0, cfg.FLOOR_1_Z + 1.0), (0, 1, 0), 2.0)
    check("upper landing connects through partition arch", not h)
    # continuous upper floor from landing into the corridor zone behind the partition
    loc, o = scene_ray((cfg.STAIR_X, -3.0, cfg.FLOOR_1_Z + 1.0), (0, 0, -1), 5.0)
    check("upper floor continues behind arch", loc is not None and abs(loc.z - cfg.FLOOR_1_Z) < 1e-4)
    # ground floor continuity
    for x, y in ((0, 4), (-14, 4), (14, 4), (0, -4), (-14, -4)):
        loc, o = scene_ray((x, y, cfg.FLOOR_G_Z + 1.0), (0, 0, -1), 3.0)
        check(f"ground floor at ({x},{y})", loc is not None and abs(loc.z - cfg.FLOOR_G_Z) < 1e-4)


def test_dimensions_and_transforms():
    print("[dimensions / transforms]")
    for n in ("Wall_G_Front", "Wall_G_Back", "Wall_1_Front", "Roof_Main"):
        o = obj(n)
        check(f"{n} dims", o and o.dimensions.x > 20 and o.dimensions.z > 0.2, str(o.dimensions if o else None))
    for o in bpy.data.objects:
        if o.get(cfg.OWNER_KEY) and o.type == 'MESH':
            if tuple(o.scale) != (1.0, 1.0, 1.0):
                check(f"unit scale {o.name}", False, str(tuple(o.scale)))
                break
    else:
        check("all owned meshes have unit scale", True)
    check("scene units metric, scale 1", bpy.context.scene.unit_settings.system == 'METRIC'
          and abs(bpy.context.scene.unit_settings.scale_length - 1.0) < 1e-9)
    # first-floor furniture sits on the floor (no floating)
    for n in ("Desk_1_0_0", "Teacher_Table_1", "Desk_G_0_0", "Reception_Counter"):
        o = obj(n)
        z0 = world_bbox(o)[0].z
        fz = cfg.FLOOR_1_Z if "_1" in n else cfg.FLOOR_G_Z
        check(f"{n} rests on floor", abs(z0 - fz) < 1e-4, f"{z0:.3f} vs {fz}")
    check("spawn point valid", cfg.SPAWN[1] > 60 and bpy.data.objects.get("Road_Main") is not None)
    for cam in (cfg.CAMERA_OVERVIEW, cfg.CAMERA_ENTRANCE):
        check(f"camera {cam}", obj(cam) and obj(cam).type == 'CAMERA')


def snapshot():
    owned = sorted(o.name for o in bpy.data.objects if o.get(cfg.OWNER_KEY) == cfg.OWNER_VALUE)
    return {"objs": owned, "cols": sorted(c.name for c in bpy.data.collections),
            "mats": sorted(m.name for m in bpy.data.materials), "lights": len(bpy.data.lights),
            "cams": len(bpy.data.cameras), "meshes": len(bpy.data.meshes)}


def test_idempotent_rebuild():
    print("[idempotency]")
    bpy.ops.mesh.primitive_cube_add(location=(100, 100, 0))
    dummy = bpy.context.active_object
    dummy.name = "UserDummy_Keep"
    before = snapshot()
    stats = builder.build_campus(log=lambda *_: None)
    after = snapshot()
    check("object names identical after 2nd build", before["objs"] == after["objs"])
    check("collections identical", before["cols"] == after["cols"])
    check("materials not duplicated", before["mats"] == after["mats"])
    check("lights/cameras not duplicated", (before["lights"], before["cams"]) == (after["lights"], after["cams"]))
    check("no orphan mesh leak", before["meshes"] == after["meshes"], f"{before['meshes']} vs {after['meshes']}")
    check("unrelated object preserved", obj("UserDummy_Keep") is not None)
    check("2nd build removed previous objects", stats["removed_previous"] == len(before["objs"]))
    bpy.data.objects.remove(dummy, do_unlink=True)
    # scene saves
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(p), copy=True)
        check("scene saves", p.exists() and p.stat().st_size > 10000)


def main():
    blend = ROOT / "output" / "imrd_campus.blend"
    check("output/imrd_campus.blend exists", blend.exists())
    if not obj("Wall_G_Front"):
        print("Open output/imrd_campus.blend before running this test.")
    test_collections_and_objects()
    test_wall_meshes_and_openings()
    test_doors()
    test_stairs()
    test_dimensions_and_transforms()
    test_idempotent_rebuild()
    fails = [r for r in results if not r[0]]
    print(f"\nGEOMETRY TESTS: {len(results) - len(fails)}/{len(results)} passed, {len(fails)} failed")
    for _, n, d in fails:
        print(f"  FAILED: {n} {d}")
    sys.exit(1 if fails else 0)


main()
