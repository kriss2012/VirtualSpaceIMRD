"""
01_build_campus.py
==================
Procedural 3D Model of RCPET IMRD Campus in Blender (bpy).
Builds:
- Campus terrain, main road with center markings, parking branch, and parking bays.
- 2-Floor Main Academic Building (Lobby, Classrooms, Stairs, Entrance Canopy, Roof).
- Front Plaza, Garden Walkway, Seating Circle, and Entrance Gate with Signage.
- Props: Street lamps, garden benches, parked cars, trees, and interior classroom desks/chairs.
- Lighting, cinematic cameras, and materials (Principled BSDF).
- Renders campus overview render and saves imrd_campus.blend.
"""

import bpy
import math
from mathutils import Vector, Euler
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BLEND_FILE = OUTPUT_DIR / "imrd_campus.blend"
OVERVIEW_RENDER = OUTPUT_DIR / "campus_overview.png"
ENTRANCE_RENDER = OUTPUT_DIR / "campus_entrance.png"

# ----------------------------------------------------------------------
# 1. CLEAN SCENE
# ----------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)

# ----------------------------------------------------------------------
# 2. COLLECTIONS SETUP
# ----------------------------------------------------------------------
scene = bpy.context.scene
root_collection = scene.collection

collections = {}
col_names = [
    "Terrain_Roads",
    "Building_Structure",
    "Interior_Furniture",
    "Props_Vehicles",
    "Vegetation",
    "Gate_Boundary",
    "Lighting_Cameras"
]

for name in col_names:
    col = bpy.data.collections.new(name)
    root_collection.children.link(col)
    collections[name] = col

def link_to_col(obj, target_col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    target_col.objects.link(obj)

# ----------------------------------------------------------------------
# 3. MATERIAL HELPER (Principled BSDF for Blender 4.x / 5.x)
# ----------------------------------------------------------------------
def create_material(name, base_color, roughness=0.6, metallic=0.0, emission_color=(0,0,0,1), emission_strength=0.0):
    mat = bpy.data.materials.new(name=name)
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (*base_color[:3], 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if emission_strength > 0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission_color[:3], 1.0)
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = (*emission_color[:3], 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat

# Palette
m_grass = create_material("Mat_Grass", (0.18, 0.45, 0.16), roughness=0.85)
m_asphalt = create_material("Mat_Asphalt", (0.15, 0.16, 0.17), roughness=0.7)
m_road_lines = create_material("Mat_RoadLines", (0.95, 0.85, 0.2), roughness=0.4)
m_paving = create_material("Mat_Paving", (0.75, 0.72, 0.65), roughness=0.6)
m_parking = create_material("Mat_Parking", (0.22, 0.23, 0.25), roughness=0.75)
m_park_lines = create_material("Mat_ParkLines", (0.9, 0.9, 0.9), roughness=0.3)

m_wall_ext = create_material("Mat_WallExt", (0.92, 0.89, 0.82), roughness=0.7)      # Cream/Beige IMRD facade
m_wall_trim = create_material("Mat_WallTrim", (0.78, 0.42, 0.18), roughness=0.5)     # Terracotta/Orange accent
m_wall_int = create_material("Mat_WallInt", (0.96, 0.95, 0.92), roughness=0.8)
m_floor_tile = create_material("Mat_FloorTile", (0.82, 0.80, 0.75), roughness=0.4)
m_glass = create_material("Mat_Glass", (0.3, 0.5, 0.7), roughness=0.1, metallic=0.2)
m_wood = create_material("Mat_Wood", (0.42, 0.25, 0.12), roughness=0.5)
m_metal_dark = create_material("Mat_MetalDark", (0.15, 0.15, 0.15), roughness=0.4, metallic=0.8)
m_board = create_material("Mat_Board", (0.08, 0.25, 0.12), roughness=0.4)
m_lamp_glow = create_material("Mat_LampGlow", (1.0, 0.95, 0.7), emission_color=(1.0, 0.95, 0.7, 1.0), emission_strength=5.0)
m_leaves = create_material("Mat_Leaves", (0.12, 0.40, 0.10), roughness=0.8)
m_trunk = create_material("Mat_Trunk", (0.32, 0.20, 0.10), roughness=0.9)

# ----------------------------------------------------------------------
# 4. PRIMITIVE BUILDERS
# ----------------------------------------------------------------------
def add_box(col, name, center, size, mat=None):
    bpy.ops.mesh.primitive_cube_add(location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    if mat:
        obj.data.materials.append(mat)
    link_to_col(obj, col)
    return obj

def add_plane(col, name, center, size, mat=None):
    bpy.ops.mesh.primitive_plane_add(location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0] / 2, size[1] / 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    if mat:
        obj.data.materials.append(mat)
    link_to_col(obj, col)
    return obj

def add_cylinder(col, name, center, radius, depth, mat=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=center)
    obj = bpy.context.active_object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    link_to_col(obj, col)
    return obj

# ----------------------------------------------------------------------
# 5. TERRAIN, ROADS & PLAZAS
# ----------------------------------------------------------------------
col_terrain = collections["Terrain_Roads"]

# Main grass ground
add_box(col_terrain, "Ground_Grass", (0, 30, -0.1), (220, 180, 0.2), m_grass)

# Main approach road (from gate at z=76 to plaza at z=20)
add_box(col_terrain, "Road_Main", (0, 48, 0.02), (9.0, 56.0, 0.04), m_asphalt)

# Yellow centre line dashes
for z in range(22, 74, 5):
    add_box(col_terrain, f"Road_Dash_{z}", (0, z, 0.045), (0.25, 2.5, 0.02), m_road_lines)

# Branch road to Parking
add_box(col_terrain, "Road_Branch_Parking", (18, 37, 0.02), (26.0, 7.0, 0.04), m_asphalt)

# Parking lot
add_box(col_terrain, "Parking_Area", (44, 43, 0.025), (34.0, 24.0, 0.04), m_parking)

# Parking bay lines
for k in range(9):
    x_pos = 30 + k * 3.4
    add_box(col_terrain, f"Parking_Line_A_{k}", (x_pos, 36, 0.05), (0.15, 6.0, 0.02), m_park_lines)
    add_box(col_terrain, f"Parking_Line_B_{k}", (x_pos, 50, 0.05), (0.15, 6.0, 0.02), m_park_lines)

# Main entrance paved plaza
add_box(col_terrain, "Plaza_Front", (0, 15, 0.03), (48.0, 10.0, 0.05), m_paving)

# Garden walkway & circular plaza
add_box(col_terrain, "Walkway_Garden_A", (-22.5, 34, 0.03), (3.0, 30.0, 0.05), m_paving)
add_box(col_terrain, "Walkway_Garden_B", (-31, 48.5, 0.03), (16.0, 3.0, 0.05), m_paving)
add_cylinder(col_terrain, "Garden_Circle_Plaza", (-40, 48.5, 0.035), radius=6.0, depth=0.04, mat=m_paving)
add_cylinder(col_terrain, "Garden_Flowerbed", (-40, 48.5, 0.08), radius=2.5, depth=0.08, mat=m_leaves)

# Parking walkway
add_box(col_terrain, "Walkway_Parking", (22.5, 27, 0.03), (3.0, 16.0, 0.05), m_paving)

# ----------------------------------------------------------------------
# 6. MAIN ACADEMIC BUILDING (2 Floors)
# Center: (0, 0), Extents: X[-20.6, 20.6], Y[-8.6, 8.6] (Z is up in Blender!)
# Coordinate mapping:
# Blender X = width (Left/Right) [-20.6, 20.6]
# Blender Y = depth (Front/Back) [-8.6, 8.6], Front is +Y, Back is -Y
# Blender Z = height (Vertical) [0.0 to 9.2m]
# ----------------------------------------------------------------------
col_bld = collections["Building_Structure"]

# Base Plinth & Entrance Steps
add_box(col_bld, "Bld_Plinth", (0, 0, 0.15), (41.6, 17.6, 0.3), m_paving)
add_box(col_bld, "Bld_Steps_1", (0, 9.4, 0.1), (14.0, 2.0, 0.2), m_paving)
add_box(col_bld, "Bld_Steps_2", (0, 10.2, 0.05), (16.0, 1.8, 0.1), m_paving)

# Ground Floor Floor Slab
add_box(col_bld, "Bld_Floor_G", (0, 0, 0.32), (41.2, 17.2, 0.04), m_floor_tile)

# Ground Floor Walls (Exterior)
# Back wall (Y = -8.5)
add_box(col_bld, "Wall_G_Back", (0, -8.5, 2.15), (41.2, 0.3, 3.7), m_wall_ext)
# Left wall (X = -20.5)
add_box(col_bld, "Wall_G_Left", (-20.5, 0, 2.15), (0.3, 17.0, 3.7), m_wall_ext)
# Right wall (X = 20.5)
add_box(col_bld, "Wall_G_Right", (20.5, 0, 2.15), (0.3, 17.0, 3.7), m_wall_ext)
# Front wall Left wing (Y = 8.5, X = -14)
add_box(col_bld, "Wall_G_Front_Left", (-13.5, 8.5, 2.15), (13.6, 0.3, 3.7), m_wall_ext)
# Front wall Right wing (Y = 8.5, X = 14)
add_box(col_bld, "Wall_G_Front_Right", (13.5, 8.5, 2.15), (13.6, 0.3, 3.7), m_wall_ext)

# Front Entrance Door Frame & Glass
add_box(col_bld, "Entrance_Frame_Left", (-3.5, 8.5, 2.15), (0.3, 0.3, 3.7), m_wall_trim)
add_box(col_bld, "Entrance_Frame_Right", (3.5, 8.5, 2.15), (0.3, 0.3, 3.7), m_wall_trim)
add_box(col_bld, "Entrance_Frame_Top", (0, 8.5, 3.65), (7.0, 0.3, 0.7), m_wall_trim)
add_box(col_bld, "Entrance_Glass_Door", (0, 8.5, 1.65), (6.4, 0.08, 3.1), m_glass)

# First Floor Slab (Separating Floor 1 and Floor 2)
add_box(col_bld, "Slab_Floor_1", (0, 0, 4.15), (41.6, 17.6, 0.3), m_paving)

# Grand Entrance Canopy & Columns
add_box(col_bld, "Canopy_Roof", (0, 10.5, 4.15), (13.0, 4.0, 0.3), m_wall_trim)
add_cylinder(col_bld, "Column_Canopy_L", (-5.5, 12.0, 2.15), radius=0.28, depth=3.7, mat=m_wall_trim)
add_cylinder(col_bld, "Column_Canopy_R", (5.5, 12.0, 2.15), radius=0.28, depth=3.7, mat=m_wall_trim)

# First Floor Walls (Exterior)
# Back wall
add_box(col_bld, "Wall_1_Back", (0, -8.5, 6.3), (41.2, 0.3, 4.0), m_wall_ext)
# Left wall
add_box(col_bld, "Wall_1_Left", (-20.5, 0, 6.3), (0.3, 17.0, 4.0), m_wall_ext)
# Right wall
add_box(col_bld, "Wall_1_Right", (20.5, 0, 6.3), (0.3, 17.0, 4.0), m_wall_ext)
# Front wall wings
add_box(col_bld, "Wall_1_Front_Left", (-13.5, 8.5, 6.3), (13.6, 0.3, 4.0), m_wall_ext)
add_box(col_bld, "Wall_1_Front_Right", (13.5, 8.5, 6.3), (13.6, 0.3, 4.0), m_wall_ext)
# First floor center windows / balcony facade
add_box(col_bld, "Wall_1_Center_Glass", (0, 8.5, 6.3), (13.0, 0.1, 3.4), m_glass)
add_box(col_bld, "Wall_1_Balcony_Rail", (0, 8.7, 5.0), (13.2, 0.15, 1.0), m_wall_trim)

# Building Roof & Parapet
add_box(col_bld, "Roof_Main", (0, 0, 8.45), (41.8, 17.8, 0.3), m_paving)
add_box(col_bld, "Parapet_Front", (0, 8.75, 9.1), (42.0, 0.3, 1.0), m_wall_trim)
add_box(col_bld, "Parapet_Back", (0, -8.75, 9.1), (42.0, 0.3, 1.0), m_wall_trim)
add_box(col_bld, "Parapet_Left", (-20.85, 0, 9.1), (0.3, 17.6, 1.0), m_wall_trim)
add_box(col_bld, "Parapet_Right", (20.85, 0, 9.1), (0.3, 17.6, 1.0), m_wall_trim)

# Building Signage Panel on Canopy: "RCPET IMRD SHIRPUR"
sign_panel = add_box(col_bld, "Building_Sign_Panel", (0, 12.35, 4.3), (11.0, 0.2, 0.8), m_wall_trim)

# Central Staircase (Ground to First Floor)
for step in range(16):
    s_z = 0.45 + step * 0.23
    s_y = 2.0 - step * 0.35
    add_box(col_bld, f"Stair_Step_{step}", (0, s_y, s_z), (3.2, 0.35, 0.23), m_paving)

# Interior Partition Walls (Corridors & Classrooms)
add_box(col_bld, "Wall_Int_Corridor_G", (0, 0, 2.15), (40.8, 0.2, 3.7), m_wall_int)
add_box(col_bld, "Wall_Int_Class_L1", (-8.0, 4.2, 2.15), (0.2, 8.2, 3.7), m_wall_int)
add_box(col_bld, "Wall_Int_Class_R1", (8.0, 4.2, 2.15), (0.2, 8.2, 3.7), m_wall_int)
add_box(col_bld, "Wall_Int_Corridor_1", (0, 0, 6.3), (40.8, 0.2, 4.0), m_wall_int)

# Classroom Windows (Exterior front facade cutouts / glass panes)
for side in [-1, 1]:
    for win_idx in range(3):
        win_x = side * (9.0 + win_idx * 4.0)
        # Ground floor window
        add_box(col_bld, f"Window_G_{side}_{win_idx}", (win_x, 8.52, 2.3), (2.8, 0.08, 1.8), m_glass)
        # First floor window
        add_box(col_bld, f"Window_1_{side}_{win_idx}", (win_x, 8.52, 6.5), (2.8, 0.08, 1.8), m_glass)

# ----------------------------------------------------------------------
# 7. INTERIOR FURNITURE (Lobby, Reception, Classrooms)
# ----------------------------------------------------------------------
col_furn = collections["Interior_Furniture"]

# Reception Counter in Entrance Lobby
add_box(col_furn, "Reception_Counter", (-3.5, 4.0, 0.8), (3.0, 1.0, 1.0), m_wood)
add_box(col_furn, "Reception_Chair", (-3.5, 3.0, 0.6), (0.6, 0.6, 0.8), m_metal_dark)

# Ground Floor Classroom Desks (Left Wing, X ~ -14, Y ~ 4.5)
add_box(col_furn, "Class_G_Blackboard", (-14.0, 0.2, 2.2), (4.5, 0.08, 1.4), m_board)
add_box(col_furn, "Teacher_Table_G", (-14.0, 1.6, 0.7), (2.2, 0.9, 0.8), m_wood)

for row in range(3):
    row_y = 3.2 + row * 1.5
    for col_idx in range(3):
        desk_x = -17.5 + col_idx * 2.8
        # Desk
        add_box(col_furn, f"Desk_G_{row}_{col_idx}", (desk_x, row_y, 0.65), (1.4, 0.6, 0.7), m_wood)
        # Bench/Chair
        add_box(col_furn, f"Bench_G_{row}_{col_idx}", (desk_x, row_y + 0.5, 0.45), (1.3, 0.35, 0.45), m_metal_dark)

# First Floor Classroom Desks (Right Wing, X ~ 14, Y ~ 4.5)
add_box(col_furn, "Class_1_Whiteboard", (14.0, 0.2, 6.4), (4.5, 0.08, 1.4), m_wall_ext)
add_box(col_furn, "Teacher_Table_1", (14.0, 1.6, 4.8), (2.2, 0.9, 0.8), m_wood)
for row in range(3):
    row_y = 3.2 + row * 1.5
    for col_idx in range(3):
        desk_x = 10.5 + col_idx * 2.8
        add_box(col_furn, f"Desk_1_{row}_{col_idx}", (desk_x, row_y, 4.75), (1.4, 0.6, 0.7), m_wood)
        add_box(col_furn, f"Bench_1_{row}_{col_idx}", (desk_x, row_y + 0.5, 4.55), (1.3, 0.35, 0.45), m_metal_dark)

# ----------------------------------------------------------------------
# 8. OUTDOOR PROPS & VEHICLES
# ----------------------------------------------------------------------
col_props = collections["Props_Vehicles"]

# Street lamps along the main approach road and plaza
lamp_coords = [
    (-5.5, 26), (5.5, 26),
    (-5.5, 42), (5.5, 42),
    (-5.5, 58), (5.5, 58),
    (-5.5, 72), (5.5, 72),
    (-16.0, 15.0), (16.0, 15.0),
    (-24.0, 48.5)
]

for i, (lx, ly) in enumerate(lamp_coords):
    # Pole
    add_cylinder(col_props, f"Lamp_Pole_{i}", (lx, ly, 2.2), radius=0.08, depth=4.4, mat=m_metal_dark)
    # Lamp head
    add_cylinder(col_props, f"Lamp_Head_{i}", (lx, ly, 4.5), radius=0.25, depth=0.25, mat=m_metal_dark)
    # Glow emitter
    add_cylinder(col_props, f"Lamp_Glow_{i}", (lx, ly, 4.35), radius=0.20, depth=0.1, mat=m_lamp_glow)

# Plaza Benches & Seating Circle Benches
bench_coords = [
    (-14, 13, 0),
    (-7, 13, 0),
    (7, 13, 0),
    (14, 13, 0),
]
for idx, (bx, by, rot) in enumerate(bench_coords):
    add_box(col_props, f"Bench_Plaza_{idx}", (bx, by, 0.45), (1.8, 0.6, 0.5), m_wood)
    add_box(col_props, f"Bench_Plaza_Back_{idx}", (bx, by - 0.25, 0.75), (1.8, 0.1, 0.5), m_wood)

# 4 Garden circle benches
for k in range(4):
    angle = k * (math.pi / 2)
    gx = -40 + math.cos(angle) * 4.2
    gy = 48.5 + math.sin(angle) * 4.2
    add_box(col_props, f"Garden_Bench_{k}", (gx, gy, 0.4), (1.6, 0.5, 0.4), m_wood)

# Parked Cars in Parking Lot
car_colors = [
    (0.85, 0.12, 0.12),  # Red
    (0.12, 0.35, 0.85),  # Blue
    (0.92, 0.92, 0.92),  # White
    (0.15, 0.15, 0.15),  # Black
    (0.88, 0.75, 0.10),  # Yellow
    (0.25, 0.65, 0.30),  # Green
]

for idx in range(6):
    cx = 32.0 + idx * 3.4
    cy = 36.0
    c_mat = create_material(f"Mat_Car_{idx}", car_colors[idx % len(car_colors)], roughness=0.3, metallic=0.7)
    # Lower body
    add_box(col_props, f"Car_{idx}_Body", (cx, cy, 0.6), (1.8, 4.0, 0.65), c_mat)
    # Cabin / Roof
    add_box(col_props, f"Car_{idx}_Cabin", (cx, cy - 0.2, 1.2), (1.6, 2.2, 0.55), m_glass)
    # Wheels
    for wx in [-0.95, 0.95]:
        for wy in [cy - 1.2, cy + 1.2]:
            add_cylinder(col_props, f"Car_{idx}_Wheel", (cx + wx, wy, 0.32), radius=0.32, depth=0.2, mat=m_metal_dark)

# ----------------------------------------------------------------------
# 9. CAMPUS ENTRANCE GATE & ARCHWAY
# Gate located at Y = 74.0 (Main entrance from highway/approach)
# ----------------------------------------------------------------------
col_gate = collections["Gate_Boundary"]

# Gate Pillars
add_box(col_gate, "Gate_Pillar_L", (-5.5, 75.0, 2.8), (1.2, 1.2, 5.6), m_wall_trim)
add_box(col_gate, "Gate_Pillar_R", (5.5, 75.0, 2.8), (1.2, 1.2, 5.6), m_wall_trim)
# Gate Overhead Arch Beam
add_box(col_gate, "Gate_Arch_Beam", (0, 75.0, 5.6), (12.2, 1.4, 0.8), m_wall_trim)
# Gate Main Signboard: "RCPET IMRD SHIRPUR"
add_box(col_gate, "Gate_Signboard", (0, 75.0, 6.3), (10.0, 0.2, 0.9), m_wall_ext)
# Security Guard Cabin
add_box(col_gate, "Security_Cabin", (7.8, 73.5, 1.6), (2.8, 2.8, 3.2), m_wall_ext)
add_box(col_gate, "Security_Cabin_Roof", (7.8, 73.5, 3.3), (3.2, 3.2, 0.3), m_wall_trim)
add_box(col_gate, "Security_Cabin_Window", (6.4, 73.5, 1.6), (0.1, 1.6, 1.2), m_glass)

# Perimeter Wall / Fence segments
add_box(col_gate, "Boundary_Wall_L", (-25.0, 75.0, 1.1), (38.0, 0.4, 2.2), m_wall_ext)
add_box(col_gate, "Boundary_Wall_R", (25.0, 75.0, 1.1), (38.0, 0.4, 2.2), m_wall_ext)

# ----------------------------------------------------------------------
# 10. VEGETATION (Trees & Bushes)
# ----------------------------------------------------------------------
col_veg = collections["Vegetation"]

def add_tree(col, name, center, height=5.5):
    trunk_h = height * 0.45
    crown_r = height * 0.45
    # Trunk
    add_cylinder(col, f"{name}_Trunk", (center[0], center[1], trunk_h / 2), radius=0.25, depth=trunk_h, mat=m_trunk)
    # Foliage layers
    add_cylinder(col, f"{name}_Crown1", (center[0], center[1], trunk_h + crown_r * 0.6), radius=crown_r, depth=crown_r * 1.2, mat=m_leaves)
    add_cylinder(col, f"{name}_Crown2", (center[0], center[1], trunk_h + crown_r * 1.3), radius=crown_r * 0.75, depth=crown_r, mat=m_leaves)

tree_positions = [
    # Along approach road
    (-8.5, 24), (-8.5, 38), (-8.5, 52), (-8.5, 66),
    (8.5, 24), (8.5, 52), (8.5, 66),
    # Around the garden
    (-32, 38), (-48, 38), (-32, 58), (-48, 58),
    (-40, 62), (-54, 48), (-28, 48),
    # Behind the main building
    (-15, -12), (0, -12), (15, -12),
    # Border near parking
    (60, 36), (60, 48), (60, 60)
]

for idx, (tx, ty) in enumerate(tree_positions):
    add_tree(col_veg, f"Tree_{idx}", (tx, ty, 0), height=5.0 + (idx % 3) * 0.8)

# ----------------------------------------------------------------------
# 11. LIGHTING & CAMERAS
# ----------------------------------------------------------------------
col_light = collections["Lighting_Cameras"]

# Sunlight / Daylight
sun_data = bpy.data.lights.new(name="Sun_Daylight", type='SUN')
sun_data.energy = 4.5
sun_data.color = (1.0, 0.98, 0.92)
sun_obj = bpy.data.objects.new(name="Sun_Daylight", object_data=sun_data)
sun_obj.location = (20, -20, 40)
sun_obj.rotation_euler = Euler((math.radians(45), math.radians(20), math.radians(35)), 'XYZ')
col_light.objects.link(sun_obj)

# Soft Sky Fill Light
fill_data = bpy.data.lights.new(name="Sky_Fill", type='SUN')
fill_data.energy = 1.8
fill_data.color = (0.7, 0.85, 1.0)
fill_obj = bpy.data.objects.new(name="Sky_Fill", object_data=fill_data)
fill_obj.location = (-20, 20, 35)
fill_obj.rotation_euler = Euler((math.radians(-50), math.radians(-30), math.radians(-120)), 'XYZ')
col_light.objects.link(fill_obj)

# Camera 1: Campus Overview (High angle isometric-style view)
cam_overview_data = bpy.data.cameras.new("Cam_Overview")
cam_overview_data.lens = 35
cam_overview_data.clip_end = 400
cam_overview = bpy.data.objects.new("Cam_Overview", cam_overview_data)
cam_overview.location = (65, 105, 55)
cam_overview.rotation_euler = Euler((math.radians(64), math.radians(0), math.radians(145)), 'XYZ')
col_light.objects.link(cam_overview)

# Camera 2: Entrance Approach (View from Gate towards Building)
cam_entrance_data = bpy.data.cameras.new("Cam_Entrance")
cam_entrance_data.lens = 28
cam_entrance_data.clip_end = 300
cam_entrance = bpy.data.objects.new("Cam_Entrance", cam_entrance_data)
cam_entrance.location = (0, 72, 2.2)
cam_entrance.rotation_euler = Euler((math.radians(85), math.radians(0), math.radians(180)), 'XYZ')
col_light.objects.link(cam_entrance)

# Set Overview camera as active
scene.camera = cam_overview

# ----------------------------------------------------------------------
# 12. RENDER SETUP & EXPORT
# ----------------------------------------------------------------------
# Configure Render Engine
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

print("\n[IMRD Builder] Rendering campus overview...")
scene.render.filepath = str(OVERVIEW_RENDER)
try:
    bpy.ops.render.render(write_still=True)
    print(f"[IMRD Builder] Overview rendered to: {OVERVIEW_RENDER}")
except Exception as e:
    print(f"[IMRD Builder] Render overview warning: {e}")

# Render Entrance shot
print("[IMRD Builder] Rendering entrance perspective...")
scene.camera = cam_entrance
scene.render.filepath = str(ENTRANCE_RENDER)
try:
    bpy.ops.render.render(write_still=True)
    print(f"[IMRD Builder] Entrance rendered to: {ENTRANCE_RENDER}")
except Exception as e:
    print(f"[IMRD Builder] Render entrance warning: {e}")

# Restore overview camera
scene.camera = cam_overview

# Save Blender Main File
print(f"[IMRD Builder] Saving Blender main file: {BLEND_FILE}")
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_FILE))
print("[IMRD Builder] Done! IMRD campus successfully built and saved.")
