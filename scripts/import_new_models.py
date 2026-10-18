"""
import_new_models.py
====================
Robust, scale-normalized integration of all 3D assets from assets/New Modle
into the IMRD Campus Scene.
"""

import bpy
import bmesh
import math
from pathlib import Path
from mathutils import Vector, Euler, Matrix

PROJECT_ROOT = Path(r"C:\Users\krish\.gemini\antigravity-ide\scratch\IMRD-Blender-Game")
ASSETS_DIR = PROJECT_ROOT / "assets" / "New Modle"
OUTPUT_DIR = PROJECT_ROOT / "output"
BLEND_FILE = OUTPUT_DIR / "imrd_campus.blend"

OWNER_KEY = "imrd_owner"
OWNER_VALUE = "new_models"


def ensure_collection(col_name="Imported_Assets"):
    col = bpy.data.collections.get(col_name)
    if col is None:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)
    col[OWNER_KEY] = OWNER_VALUE
    return col


def clear_previous():
    removed = 0
    for o in list(bpy.data.objects):
        if o.get(OWNER_KEY) == OWNER_VALUE or o.name.startswith("Root_") or o.name.startswith("Helipad_"):
            bpy.data.objects.remove(o, do_unlink=True)
            removed += 1
    print(f"[Import Models] Cleared {removed} previous imported objects.")


def append_library_objects(blend_file, name_filter=None):
    p = Path(blend_file)
    if not p.exists():
        print(f"[Warning] Asset file not found: {p}")
        return []
    
    with bpy.data.libraries.load(str(p)) as (df, dt):
        candidates = []
        for name in df.objects:
            if any(name.startswith(t) for t in ("Camera", "Light", "Sun", "Point")):
                continue
            if name_filter is None or name_filter(name):
                candidates.append(name)
        dt.objects = candidates

    loaded = [o for o in dt.objects if o is not None]
    return loaded


def place_model_hierarchy(objs, asset_name, target_pos, target_size, target_axis='MAX', rot_euler=(0, 0, 0), target_col=None):
    """
    Robust hierarchy placement algorithm:
    - Finds all top-level root objects and parents them to a single Master Empty.
    - Computes composite world bounding box across all constituent meshes.
    - Scales the Master Empty to match target_size without double-transform bugs.
    - Accurately ground-snaps so the lowest mesh vertex rests flush on target surface.
    """
    if not objs:
        return None
    
    col = target_col or ensure_collection("Imported_Assets")
    
    # 1. Ensure all loaded objects are tagged and in collection
    for o in objs:
        o[OWNER_KEY] = OWNER_VALUE
        if o.name not in col.objects:
            col.objects.link(o)
            
    # 2. Find root objects
    roots = [o for o in objs if o.parent is None]
    master = bpy.data.objects.new(f"Root_{asset_name}", None)
    master.empty_display_type = 'PLAIN_AXES'
    master[OWNER_KEY] = OWNER_VALUE
    col.objects.link(master)
    master.location = Vector((0, 0, 0))
    master.rotation_euler = Euler((0, 0, 0), 'XYZ')
    master.scale = Vector((1, 1, 1))
    
    for r in roots:
        r.parent = master
        
    bpy.context.view_layer.update()
    
    # 3. Compute composite bounding box
    meshes = [o for o in objs if o.type == 'MESH']
    if not meshes:
        master.location = Vector(target_pos)
        return master

    min_co = Vector((float('inf'), float('inf'), float('inf')))
    max_co = Vector((float('-inf'), float('-inf'), float('-inf')))
    for m in meshes:
        for c in m.bound_box:
            wco = m.matrix_world @ Vector(c)
            min_co.x = min(min_co.x, wco.x)
            min_co.y = min(min_co.y, wco.y)
            min_co.z = min(min_co.z, wco.z)
            max_co.x = max(max_co.x, wco.x)
            max_co.y = max(max_co.y, wco.y)
            max_co.z = max(max_co.z, wco.z)
            
    dims = max_co - min_co
    if target_axis == 'X':
        curr_len = dims.x
    elif target_axis == 'Y':
        curr_len = dims.y
    elif target_axis == 'Z':
        curr_len = dims.z
    else:
        curr_len = max(dims.x, dims.y, dims.z)
        
    scale_factor = target_size / max(0.001, curr_len)
    master.scale = Vector((scale_factor, scale_factor, scale_factor))
    master.rotation_euler = Euler(rot_euler, 'XYZ')
    
    bpy.context.view_layer.update()
    
    # 4. Compute min Z after scale and rotation
    min_z = float('inf')
    for m in meshes:
        for c in m.bound_box:
            min_z = min(min_z, (m.matrix_world @ Vector(c)).z)
            
    bottom_offset = min_z - master.location.z
    
    # 5. Move master to target position with exact ground snap
    master.location.x = target_pos[0]
    master.location.y = target_pos[1]
    master.location.z = target_pos[2] - bottom_offset
    
    bpy.context.view_layer.update()
    
    final_min_z = min((m.matrix_world @ Vector(c)).z for m in meshes for c in m.bound_box)
    print(f"[{asset_name}] Successfully placed at {master.location}, Ground Z: {final_min_z:.3f}")
    return master


# ----------------------------------------------------------------------
# HELIPAD CONSTRUCTION
# ----------------------------------------------------------------------
def build_executive_helipad(target_col, center=(42.0, 50.0, 0.02)):
    cx, cy, cz = center
    mats = bpy.data.materials
    asphalt_mat = mats.get("Mat_Asphalt") or mats.get("Mat_Parking")
    curb_mat = mats.get("Mat_Curb") or mats.get("Mat_WallTrim")
    lines_mat = mats.get("Mat_RoadLines") or mats.get("Mat_ParkLines")
    white_mat = mats.get("Mat_ParkLines") or mats.get("Mat_Ceiling")
    glow_mat = mats.get("Mat_LampGlow")
    
    def box(name, c, s, mat):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
        bmesh.ops.translate(bm, vec=Vector(c))
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(name, me)
        if mat:
            me.materials.append(mat)
        obj[OWNER_KEY] = OWNER_VALUE
        target_col.objects.link(obj)
        return obj

    def cyl(name, c, r, depth, mat, segments=36):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                              radius1=r, radius2=r, depth=depth)
        bmesh.ops.translate(bm, vec=Vector(c))
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(name, me)
        if mat:
            me.materials.append(mat)
        obj[OWNER_KEY] = OWNER_VALUE
        target_col.objects.link(obj)
        return obj

    cyl("Helipad_Base_Pad", (cx, cy, cz + 0.04), 7.0, 0.08, curb_mat, segments=36)
    cyl("Helipad_Border_Ring", (cx, cy, cz + 0.045), 6.6, 0.082, lines_mat, segments=36)
    cyl("Helipad_Inner_Surface", (cx, cy, cz + 0.047), 6.2, 0.084, asphalt_mat, segments=36)
    
    # White letter H
    h_w, h_l, h_t = 0.55, 4.2, 0.02
    box("Helipad_Letter_H_Left", (cx - 1.4, cy, cz + 0.09), (h_w, h_l, h_t), white_mat)
    box("Helipad_Letter_H_Right", (cx + 1.4, cy, cz + 0.09), (h_w, h_l, h_t), white_mat)
    box("Helipad_Letter_H_Cross", (cx, cy, cz + 0.09), (2.8, h_w, h_t), white_mat)
    
    for i in range(8):
        ang = i * (2.0 * math.pi / 8.0)
        lx = cx + 6.8 * math.cos(ang)
        ly = cy + 6.8 * math.sin(ang)
        cyl(f"Helipad_Beacon_Base_{i}", (lx, ly, cz + 0.12), 0.14, 0.18, curb_mat, segments=12)
        cyl(f"Helipad_Beacon_Lens_{i}", (lx, ly, cz + 0.22), 0.09, 0.10, glow_mat, segments=12)

    print(f"[Import Models] Built Executive Helipad at ({cx}, {cy})")


# ----------------------------------------------------------------------
# MASTER INTEGRATION RUNNER
# ----------------------------------------------------------------------
def import_all():
    print("\n=======================================================")
    print("STARTING ROBUST ASSET INTEGRATION INTO SCENE...")
    print("=======================================================")
    
    target_col = ensure_collection("Imported_Assets")
    clear_previous()
    
    # 1. Mercedes-Benz GLS 580 (Parking Bay 1)
    p_merc = ASSETS_DIR / "32-mercedes-benz-gls-580-2020" / "uploads_files_2787791_Mercedes+Benz+GLS+580.blend"
    merc_objs = append_library_objects(p_merc, name_filter=lambda n: "mercedes" in n.lower() or "cylinder" in n.lower())
    place_model_hierarchy(merc_objs, "Mercedes_GLS580", (30.0, 36.0, 0.025), 5.20, target_axis='Y', rot_euler=(0, 0, 0), target_col=target_col)
    
    # 2. Ford Mustang (Parking Bay 2)
    p_mustang = ASSETS_DIR / "26-mustang-13.04.2021-compressed" / "Mustang 13.04.2021 Compressed.blend"
    mustang_objs = append_library_objects(p_mustang, name_filter=lambda n: not n.startswith("Point") and not n.startswith("Plane.001"))
    place_model_hierarchy(mustang_objs, "Ford_Mustang", (33.8, 36.0, 0.025), 4.78, target_axis='Y', rot_euler=(0, 0, 0), target_col=target_col)

    # 3. Compact Car (Parking Bay 3)
    p_car2 = ASSETS_DIR / "43-202009122216-2" / "202009122216-2.blend"
    car2_objs = append_library_objects(p_car2, name_filter=lambda n: n != "Plane")
    place_model_hierarchy(car2_objs, "City_Car_2", (37.6, 36.0, 0.025), 4.10, target_axis='Y', rot_euler=(0, 0, 0), target_col=target_col)

    # 4. Red Sports Bike (Covered Bike Station)
    p_bike = ASSETS_DIR / "41-bikered" / "bikered.blend"
    bike_objs = append_library_objects(p_bike, name_filter=lambda n: n != "Plane")
    place_model_hierarchy(bike_objs, "Red_Sport_Bike", (26.8, 46.0, 0.04), 2.15, target_axis='MAX', rot_euler=(0, 0, math.radians(90)), target_col=target_col)

    # 5. Helipad and Bell Helicopter
    build_executive_helipad(target_col, center=(42.0, 50.0, 0.02))
    p_heli = ASSETS_DIR / "87-heli_bell" / "Heli_Bell" / "Material" / "Heli_bell.blend"
    heli_objs = append_library_objects(p_heli, name_filter=lambda n: not n.startswith("Camera") and not n.startswith("Point") and n != "tanah")
    place_model_hierarchy(heli_objs, "Bell_Helicopter", (42.0, 50.0, 0.09), 11.5, target_axis='MAX', rot_euler=(0, 0, math.radians(-35)), target_col=target_col)

    # 6. High-detail Office Chairs
    p_chair = ASSETS_DIR / "19-office-chair" / "Office Chair.blend"
    chair_locs = [
        ("Reception", (-3.5, 3.2, 0.34), math.radians(180)),
        ("Classroom", (-14.0, 1.0, 0.34), math.radians(0)),
        ("ComputerLab", (14.0, 1.0, 0.34), math.radians(0)),
    ]
    for lbl, loc, rz in chair_locs:
        c_objs = append_library_objects(p_chair, name_filter=lambda n: "chair" in n.lower() or "cube" in n.lower() or "cylinder" in n.lower())
        place_model_hierarchy(c_objs, f"Office_Chair_{lbl}", loc, 0.95, target_axis='Z', rot_euler=(0, 0, rz), target_col=target_col)

    # 7. Golden Wolf Campus Mascot on Pedestal
    p_wolf = ASSETS_DIR / "88-blend" / "Blend" / "Wolf_With_Baked_Action_Animations_For_Export_One_Mesh.blend"
    wolf_objs = append_library_objects(p_wolf, name_filter=lambda n: "wolf" in n.lower() and not "skeleton" in n.lower())
    
    # Build carved pedestal at (-7.5, 17.5, 0.035)
    cx, cy, cz = -7.5, 17.5, 0.035
    mats = bpy.data.materials
    paving_mat = mats.get("Mat_Paving") or mats.get("Mat_WallTrim")
    gold_mat = mats.get("Mat_BrassGold") or mats.get("Mat_Brass")
    
    def b_box(name, c, s, mat):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
        bmesh.ops.translate(bm, vec=Vector(c))
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(name, me)
        if mat:
            me.materials.append(mat)
        obj[OWNER_KEY] = OWNER_VALUE
        target_col.objects.link(obj)
        return obj

    b_box("Mascot_Pedestal_Tier1", (cx, cy, cz + 0.20), (2.2, 1.6, 0.40), paving_mat)
    b_box("Mascot_Pedestal_Tier2", (cx, cy, cz + 0.50), (1.8, 1.2, 0.30), paving_mat)
    b_box("Mascot_Plaque", (cx, cy + 0.62, cz + 0.48), (1.1, 0.03, 0.22), gold_mat)

    for o in wolf_objs:
        if gold_mat and o.type == 'MESH':
            o.data.materials.clear()
            o.data.materials.append(gold_mat)
    place_model_hierarchy(wolf_objs, "Golden_Wolf_Mascot", (cx, cy, cz + 0.65), 1.35, target_axis='Y', rot_euler=(0, 0, math.radians(180)), target_col=target_col)

    # 8. Student Characters
    p_girl = ASSETS_DIR / "50-girl-blend" / "Girl.blend"
    girl_objs = append_library_objects(p_girl, name_filter=lambda n: n in ("Head", "Top", "hair", "scarf", "rig"))
    place_model_hierarchy(girl_objs, "Student_Girl", (-3.0, 32.0, 0.035), 1.68, target_axis='Z', rot_euler=(0, 0, math.radians(-15)), target_col=target_col)

    p_anime = ASSETS_DIR / "91-anime_character" / "Anime_charcter.blend"
    anime_objs = append_library_objects(p_anime, name_filter=lambda n: "cuerpo" in n.lower() or "cabeza" in n.lower())
    place_model_hierarchy(anime_objs, "Student_Anime", (-24.0, 34.0, 0.035), 1.70, target_axis='Z', rot_euler=(0, 0, math.radians(45)), target_col=target_col)

    # 9. Realistic 3D Trees and Grass
    p_tree = ASSETS_DIR / "60-tree" / "Tree.blend"
    for ti, (tx, ty) in enumerate([(-38.0, 34.0), (-46.0, 52.0), (36.0, 28.0)]):
        t_objs = append_library_objects(p_tree, name_filter=lambda n: "plane" in n.lower())
        place_model_hierarchy(t_objs, f"Realistic_Tree_{ti}", (tx, ty, 0.0), 6.5, target_axis='Z', rot_euler=(0, 0, math.radians(ti * 50)), target_col=target_col)

    p_grass = ASSETS_DIR / "24-grass" / "Grass" / "Grass.blend"
    for gi, (gx, gy) in enumerate([(-40.0, 43.0), (-34.0, 48.0), (0.0, 18.0), (42.0, 43.0)]):
        g_objs = append_library_objects(p_grass, name_filter=lambda n: "grass" in n.lower())
        place_model_hierarchy(g_objs, f"Grass_Tuft_{gi}", (gx, gy, 0.03), 0.35, target_axis='Z', target_col=target_col)

    # Physics pass
    for o in target_col.objects:
        if o.type == 'MESH' and o.rigid_body is None and not o.name.startswith("Grass_"):
            try:
                bpy.context.view_layer.objects.active = o
                bpy.ops.rigidbody.object_add(type='PASSIVE')
                o.rigid_body.collision_shape = 'CONVEX_HULL'
                o.rigid_body.friction = 0.6
            except Exception:
                pass

    total = len(target_col.objects)
    print(f"\n[Import Models] All models successfully imported and positioned! Total objects in collection: {total}")
    
    if BLEND_FILE.exists():
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_FILE))
        print(f"[Import Models] Saved updated master file to: {BLEND_FILE}")

    return total

if __name__ == "__main__":
    import_all()
