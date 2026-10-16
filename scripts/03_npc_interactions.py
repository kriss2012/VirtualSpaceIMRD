"""
03_npc_interactions.py
======================
NPCs and Proximity Interaction System for modern Blender.
Implements:
- Campus Guide NPC (Prof. Sharma) at entrance plaza.
- Student NPCs (Aarav at plaza, Pooja at garden seating circle).
- Collectible Golden Student ID Card with glow shader in the garden.
- Interactive swinging door at main entrance.
- Reusable proximity detection system for [E] key interaction.
- Multi-step dialogue trees and inventory collection.
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
NPC_RENDER = OUTPUT_DIR / "npc_guide_entrance.png"

# ----------------------------------------------------------------------
# 1. MATERIAL HELPER (Evaluated after file load)
# ----------------------------------------------------------------------
def get_or_create_mat(name, color, roughness=0.6, emission_color=(0,0,0,1), emission_strength=0.0):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name=name)
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if emission_strength > 0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission_color[:3], 1.0)
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = (*emission_color[:3], 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat

# ----------------------------------------------------------------------
# 2. SPAWN NPCS & PROPS
# ----------------------------------------------------------------------
def spawn_npc(col, name, loc, rot_z, shirt_mat, skin_mat, suit_mat, hair_mat, marker_mat, title_label="Student"):
    """Spawns a clean 3D humanoid NPC with title banner."""
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=loc)
    root = bpy.context.active_object
    root.name = name
    root.rotation_euler.z = rot_z
    for c in list(root.users_collection):
        c.objects.unlink(root)
    col.objects.link(root)

    def add_mesh_part(p_name, p_type, p_loc, p_scale, p_mat):
        if p_type == 'CUBE':
            bpy.ops.mesh.primitive_cube_add(location=p_loc)
        elif p_type == 'SPHERE':
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=p_loc)
        elif p_type == 'CYLINDER':
            bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=1.0, location=p_loc)
        p = bpy.context.active_object
        p.name = f"{name}_{p_name}"
        p.scale = p_scale
        bpy.ops.object.transform_apply(scale=True)
        if p_mat:
            p.data.materials.append(p_mat)
        for c in list(p.users_collection):
            c.objects.unlink(p)
        col.objects.link(p)
        p.parent = root
        return p

    # Body
    add_mesh_part("Torso", 'CUBE', (loc[0], loc[1], loc[2] + 1.15), (0.28, 0.18, 0.40), shirt_mat)
    # Head & Hair
    add_mesh_part("Head", 'SPHERE', (loc[0], loc[1], loc[2] + 1.70), (0.16, 0.16, 0.18), skin_mat)
    add_mesh_part("Hair", 'SPHERE', (loc[0], loc[1], loc[2] + 1.76), (0.17, 0.17, 0.14), hair_mat)
    # Legs
    add_mesh_part("Leg_L", 'CYLINDER', (loc[0] - 0.14, loc[1], loc[2] + 0.50), (0.09, 0.09, 0.70), suit_mat)
    add_mesh_part("Leg_R", 'CYLINDER', (loc[0] + 0.14, loc[1], loc[2] + 0.50), (0.09, 0.09, 0.70), suit_mat)
    # Floating Marker
    add_mesh_part("Marker", 'SPHERE', (loc[0], loc[1], loc[2] + 2.15), (0.08, 0.08, 0.08), marker_mat)

    return root

def setup_all_npcs_and_interactives():
    col_name = "NPCs_and_Interactives"
    if col_name in bpy.data.collections:
        col = bpy.data.collections[col_name]
    else:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)

    # Clear existing objects in this collection
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    # Initialize materials within active blend context
    m_skin = get_or_create_mat("Mat_NPCSkin", (0.82, 0.62, 0.48), roughness=0.7)
    m_guide_suit = get_or_create_mat("Mat_GuideSuit", (0.15, 0.22, 0.28), roughness=0.5)
    m_student_a = get_or_create_mat("Mat_StudentA_Shirt", (0.2, 0.55, 0.35), roughness=0.6)
    m_student_b = get_or_create_mat("Mat_StudentB_Shirt", (0.7, 0.25, 0.55), roughness=0.6)
    m_hair_dark = get_or_create_mat("Mat_NPCHair", (0.05, 0.04, 0.03), roughness=0.9)
    m_id_card = get_or_create_mat("Mat_GoldIDCard", (1.0, 0.85, 0.2), roughness=0.2, emission_color=(1.0, 0.85, 0.2, 1.0), emission_strength=3.5)
    m_door_wood = get_or_create_mat("Mat_InteractiveDoor", (0.45, 0.28, 0.15), roughness=0.4)
    m_marker = get_or_create_mat("Mat_NPCMarker", (0.2, 0.8, 1.0), emission_color=(0.2, 0.8, 1.0, 1.0), emission_strength=4.0)

    # 1. Campus Guide: Prof. Sharma at Main Entrance Plaza (0, 15.5, 0.03)
    guide = spawn_npc(col, "NPC_CampusGuide", (0, 15.5, 0.03), math.pi, m_guide_suit, m_skin, m_guide_suit, m_hair_dark, m_marker, "Prof. Sharma")

    # 2. Student Aarav at Plaza Benches (-7.5, 14.5, 0.03)
    aarav = spawn_npc(col, "NPC_Student_Aarav", (-7.5, 14.5, 0.03), math.pi * 0.25, m_student_a, m_skin, m_guide_suit, m_hair_dark, m_marker, "Aarav")

    # 3. Student Pooja at Garden Seating Circle (-40.0, 48.5, 0.03)
    pooja = spawn_npc(col, "NPC_Student_Pooja", (-38.5, 48.5, 0.03), -math.pi * 0.5, m_student_b, m_skin, m_guide_suit, m_hair_dark, m_marker, "Pooja")

    # 4. Collectible Golden Student ID Card in Garden
    bpy.ops.mesh.primitive_cube_add(location=(-41.2, 50.2, 0.35))
    id_card = bpy.context.active_object
    id_card.name = "Item_StudentIDCard"
    id_card.scale = (0.22, 0.35, 0.03)
    id_card.rotation_euler = Euler((math.radians(25), math.radians(15), math.radians(40)), 'XYZ')
    bpy.ops.object.transform_apply(scale=True)
    id_card.data.materials.append(m_id_card)
    for c in list(id_card.users_collection):
        c.objects.unlink(id_card)
    col.objects.link(id_card)

    # 5. Interactive Main Entrance Door Leaf
    # Phase 2: 01_build_campus.py now builds a hinged leaf with this stable name
    # (origin at the hinge). Reuse it; fall back to the legacy slab only if absent.
    door = bpy.data.objects.get("Interactive_Entrance_Door")
    if door is None:
        bpy.ops.mesh.primitive_cube_add(location=(1.5, 8.5, 1.65))
        door = bpy.context.active_object
        door.name = "Interactive_Entrance_Door"
        door.scale = (1.5, 0.08, 1.55)
        bpy.ops.object.transform_apply(scale=True)
        door.data.materials.append(m_door_wood)
        for c in list(door.users_collection):
            c.objects.unlink(door)
        col.objects.link(door)

    return guide, aarav, pooja, id_card, door

# ----------------------------------------------------------------------
# 3. INTERACTION DATABASE & LOGIC
# ----------------------------------------------------------------------
INTERACTION_REGISTRY = [
    {
        "id": "npc_guide",
        "name": "Prof. Sharma (Campus Guide)",
        "type": "NPC",
        "pos": Vector((0, 15.5, 0.0)),
        "radius": 3.2,
        "prompt": "[E] Talk to Prof. Sharma",
        "dialogue": [
            "Namaste! Welcome to RCPET's IMRD Campus, Shirpur.",
            "I am Professor Sharma. Our campus features advanced computer labs, library, and modern classrooms.",
            "MISSION 1 COMPLETE: Met the Campus Guide (+100 XP)!",
            "Next Goal: A 1st-year MCA student lost their ID card in the garden. Can you find it?"
        ]
    },
    {
        "id": "npc_aarav",
        "name": "Aarav (MCA Student)",
        "type": "NPC",
        "pos": Vector((-7.5, 14.5, 0.0)),
        "radius": 2.8,
        "prompt": "[E] Talk to Aarav",
        "dialogue": [
            "Hey there! Are you new here?",
            "Make sure to visit the ground floor classroom and check out the first floor balcony!",
            "The campus parking lot is to the east if you have a bike or car."
        ]
    },
    {
        "id": "npc_pooja",
        "name": "Pooja (BCA Student)",
        "type": "NPC",
        "pos": Vector((-38.5, 48.5, 0.0)),
        "radius": 2.8,
        "prompt": "[E] Talk to Pooja",
        "dialogue": [
            "Hi! The IMRD garden circle is the best place to relax between lectures.",
            "Look behind the flowerbed over there — I think I saw a shiny gold ID card on the lawn!"
        ]
    },
    {
        "id": "item_id_card",
        "name": "Lost Student ID Card",
        "type": "ITEM",
        "pos": Vector((-41.2, 50.2, 0.35)),
        "radius": 2.2,
        "prompt": "[E] Pick up Lost Student ID Card",
        "dialogue": [
            "You picked up the Lost Student ID Card (Roll #2026-MCA-042)!",
            "MISSION 2 COMPLETE: Found the Lost ID Card (+250 XP)!",
            "Return it to Prof. Sharma at the entrance plaza for your final reward."
        ]
    },
    {
        "id": "door_main",
        "name": "Entrance Glass Door",
        "type": "DOOR",
        "pos": Vector((0, 8.5, 1.65)),
        "radius": 3.5,
        "prompt": "[E] Toggle Entrance Door",
        "dialogue": ["Main Entrance door toggled."]
    }
]

def get_active_interaction(player_pos):
    """Finds closest interaction within trigger distance."""
    closest = None
    min_dist = float('inf')
    for item in INTERACTION_REGISTRY:
        dist = (Vector((player_pos.x, player_pos.y, 0)) - Vector((item["pos"].x, item["pos"].y, 0))).length
        if dist <= item["radius"] and dist < min_dist:
            min_dist = dist
            closest = item
    return closest

# Standalone execution
if __name__ == "__main__":
    if BLEND_FILE.exists():
        bpy.ops.wm.open_mainfile(filepath=str(BLEND_FILE))

    guide, aarav, pooja, id_card, door = setup_all_npcs_and_interactives()

    # Camera aimed at Campus Guide
    cam_name = "Cam_GuideView"
    if cam_name in bpy.data.objects:
        cam_guide = bpy.data.objects[cam_name]
    else:
        cam_guide_data = bpy.data.cameras.new(cam_name)
        cam_guide_data.lens = 45
        cam_guide = bpy.data.objects.new(cam_name, cam_guide_data)
        bpy.context.scene.collection.objects.link(cam_guide)

    cam_guide.location = (0, 20.5, 1.8)
    cam_guide.rotation_euler = Euler((math.radians(82), 0, math.radians(180)), 'XYZ')
    bpy.context.scene.camera = cam_guide

    bpy.context.scene.render.filepath = str(NPC_RENDER)
    try:
        bpy.ops.render.render(write_still=True)
        print(f"[NPC Interactions] Rendered guide perspective to: {NPC_RENDER}")
    except Exception as e:
        print(f"[NPC Interactions] Render warning: {e}")

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_FILE))
    print(f"[NPC Interactions] Successfully spawned NPCs and saved to: {BLEND_FILE}")
