"""
02_player_controller.py
=======================
Playable Student Character & Third-Person Camera Controller for modern Blender.
Implements:
- Stylized 3D student avatar (head, blazer, backpack, legs, shoes).
- Third-person camera following player.
- Blender Modal Operator (bpy.types.Operator) processing keyboard (WASD, Shift, Space)
  and mouse events in 3D Viewport.
- Delta time calculation, gravity, jumping, ground snap, and campus bounding box collision.
- Safe start/stop controls with on-screen HUD text.
"""

import bpy
import math
import time
from mathutils import Vector, Euler
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BLEND_FILE = OUTPUT_DIR / "imrd_campus.blend"
PLAYER_RENDER = OUTPUT_DIR / "player_third_person.png"

# ----------------------------------------------------------------------
# 1. COLLISION BOUNDING BOXES FOR IMRD CAMPUS
# (Min_X, Max_X, Min_Y, Max_Y, Min_Z, Max_Z)
# ----------------------------------------------------------------------
CAMPUS_COLLIDERS = [
    # Main building exterior walls (with door gap at X: [-3.5, 3.5], Y: 8.5)
    (-20.7, -3.5, 8.3, 8.7, 0.0, 8.5),      # Front wall left
    (3.5, 20.7, 8.3, 8.7, 0.0, 8.5),       # Front wall right
    (-20.7, 20.7, -8.7, -8.3, 0.0, 8.5),     # Back wall
    (-20.7, -20.3, -8.5, 8.5, 0.0, 8.5),     # Left wall
    (20.3, 20.7, -8.5, 8.5, 0.0, 8.5),      # Right wall
    # Gate pillars & Boundary walls
    (-5.8, -5.2, 74.4, 75.6, 0.0, 6.0),
    (5.2, 5.8, 74.4, 75.6, 0.0, 6.0),
    (-44.0, -5.8, 74.8, 75.2, 0.0, 2.5),
    (5.8, 44.0, 74.8, 75.2, 0.0, 2.5),
    # Security cabin
    (6.4, 9.2, 72.1, 74.9, 0.0, 3.5),
    # Parking cars zone (Corvette Z06 bays)
    (30.0, 52.0, 33.0, 39.0, 0.0, 2.0),
    # Two-Wheeler / Bike station
    (21.5, 29.5, 47.0, 52.0, 0.0, 2.2),
    # Badminton court net and posts
    (37.7, 38.3, 1.9, 8.1, 0.0, 1.6),
    # First Floor Seminar Hall stage platform
    (11.5, 17.5, 1.0, 2.8, 4.3, 5.2),
]

def check_collision(new_pos, radius=0.45):
    """Returns True if position collides with any configured obstacle."""
    px, py, pz = new_pos.x, new_pos.y, new_pos.z
    for (min_x, max_x, min_y, max_y, min_z, max_z) in CAMPUS_COLLIDERS:
        if (min_x - radius <= px <= max_x + radius and
            min_y - radius <= py <= max_y + radius and
            min_z <= pz + 1.6 and pz <= max_z):
            return True
    return False

# ----------------------------------------------------------------------
# 2. CREATE STYLIZED 3D STUDENT AVATAR
# ----------------------------------------------------------------------
def create_material(name, color, roughness=0.6, metallic=0.0):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return mat

def build_student_character():
    """Builds a recognizable 3D student avatar with body, limbs, and backpack."""
    # Ensure collection exists
    col_name = "Player_Student"
    if col_name in bpy.data.collections:
        col = bpy.data.collections[col_name]
    else:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)

    # Remove old player objects if any
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    # Materials
    m_skin = create_material("Mat_StudentSkin", (0.85, 0.65, 0.50), roughness=0.7)
    m_jacket = create_material("Mat_IMRD_Blazer", (0.08, 0.18, 0.38), roughness=0.5) # Navy blue IMRD blazer
    m_pants = create_material("Mat_StudentPants", (0.15, 0.15, 0.18), roughness=0.6)
    m_backpack = create_material("Mat_Backpack", (0.85, 0.35, 0.10), roughness=0.4)  # Orange backpack
    m_hair = create_material("Mat_StudentHair", (0.08, 0.05, 0.04), roughness=0.9)
    m_shoes = create_material("Mat_StudentShoes", (0.9, 0.9, 0.9), roughness=0.4)

    # Root Player Object (Base transform at ground)
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 68, 0.0))
    root = bpy.context.active_object
    root.name = "Player_Root"
    for c in list(root.users_collection):
        c.objects.unlink(root)
    col.objects.link(root)

    def add_part(name, shape, loc, scale, mat):
        if shape == 'CUBE':
            bpy.ops.mesh.primitive_cube_add(location=loc)
        elif shape == 'CYLINDER':
            bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=1.0, location=loc)
        elif shape == 'SPHERE':
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=loc)
        part = bpy.context.active_object
        part.name = name
        part.scale = scale
        bpy.ops.object.transform_apply(scale=True)
        if mat:
            part.data.materials.append(mat)
        for c in list(part.users_collection):
            c.objects.unlink(part)
        col.objects.link(part)
        part.parent = root
        return part

    # Torso (Blazer)
    add_part("Player_Torso", 'CUBE', (0, 68, 1.15), (0.28, 0.18, 0.40), m_jacket)
    # Head & Hair
    add_part("Player_Head", 'SPHERE', (0, 68, 1.70), (0.16, 0.16, 0.18), m_skin)
    add_part("Player_Hair", 'SPHERE', (0, 67.98, 1.76), (0.17, 0.17, 0.14), m_hair)
    # Backpack
    add_part("Player_Backpack", 'CUBE', (0, 68.22, 1.18), (0.22, 0.12, 0.32), m_backpack)
    # Legs & Pants
    add_part("Player_Leg_L", 'CYLINDER', (-0.14, 68, 0.50), (0.09, 0.09, 0.70), m_pants)
    add_part("Player_Leg_R", 'CYLINDER', (0.14, 68, 0.50), (0.09, 0.09, 0.70), m_pants)
    # Shoes
    add_part("Player_Shoe_L", 'CUBE', (-0.14, 67.93, 0.10), (0.10, 0.20, 0.10), m_shoes)
    add_part("Player_Shoe_R", 'CUBE', (0.14, 67.93, 0.10), (0.10, 0.20, 0.10), m_shoes)

    # ------------------------------------------------------------------
    # Third-Person Camera Rig
    # ------------------------------------------------------------------
    cam_name = "Player_Camera_3rd"
    if cam_name in bpy.data.objects:
        cam_obj = bpy.data.objects[cam_name]
    else:
        cam_data = bpy.data.cameras.new(cam_name)
        cam_data.lens = 32
        cam_data.clip_start = 0.2
        cam_data.clip_end = 350
        cam_obj = bpy.data.objects.new(cam_name, cam_data)
        col.objects.link(cam_obj)

    # Positioned behind student looking forward along -Y toward campus
    cam_obj.location = (0, 74.0, 2.5)
    cam_obj.rotation_euler = Euler((math.radians(78), 0, math.radians(180)), 'XYZ')

    bpy.context.scene.camera = cam_obj
    return root, cam_obj

# ----------------------------------------------------------------------
# 3. INTERACTIVE BLENDER MODAL OPERATOR
# ----------------------------------------------------------------------
class IMRD_OT_PlayerController(bpy.types.Operator):
    """Interactive Third-Person Student Player Controller for IMRD Campus"""
    bl_idname = "imrd.player_controller"
    bl_label = "IMRD Student Player Controller"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    last_time = 0.0

    # Controls state
    keys = {
        'FORWARD': False,
        'BACKWARD': False,
        'LEFT': False,
        'RIGHT': False,
        'SPRINT': False,
        'JUMP': False,
    }

    # Movement physics parameters
    walk_speed = 6.0      # m/s
    sprint_mult = 1.8     # multiplier
    jump_strength = 6.5   # m/s
    gravity = 18.0        # m/s^2
    velocity_z = 0.0
    is_grounded = True

    # Camera settings
    cam_distance = 5.2
    cam_height = 2.4
    cam_yaw = math.pi     # Faces -Y towards building
    cam_pitch = 0.20      # Slight downward angle

    def modal(self, context, event):
        # Allow Esc or Q to gracefully exit
        if event.type in {'ESC', 'Q'} and event.value == 'PRESS':
            self.cancel(context)
            self.report({'INFO'}, "[IMRD Game] Exited player controller.")
            return {'CANCELLED'}

        # Process Keyboard Inputs
        if event.type in {'W', 'UP_ARROW'}:
            self.keys['FORWARD'] = (event.value == 'PRESS')
        elif event.type in {'S', 'DOWN_ARROW'}:
            self.keys['BACKWARD'] = (event.value == 'PRESS')
        elif event.type in {'A', 'LEFT_ARROW'}:
            self.keys['LEFT'] = (event.value == 'PRESS')
        elif event.type in {'D', 'RIGHT_ARROW'}:
            self.keys['RIGHT'] = (event.value == 'PRESS')
        elif event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self.keys['SPRINT'] = (event.value == 'PRESS')
        elif event.type == 'SPACE' and event.value == 'PRESS':
            if self.is_grounded:
                self.velocity_z = self.jump_strength
                self.is_grounded = False

        # Mouse Look
        if event.type == 'MOUSEMOVE':
            dx = event.mouse_x - event.mouse_prev_x
            dy = event.mouse_y - event.mouse_prev_y
            self.cam_yaw -= dx * 0.004
            self.cam_pitch = max(-0.35, min(0.65, self.cam_pitch + dy * 0.003))

        # Main Physics / Movement update on timer tick
        if event.type == 'TIMER':
            now = time.time()
            dt = min(0.08, now - self.last_time) if self.last_time > 0 else 0.016
            self.last_time = now

            self.update_movement(context, dt)

        return {'RUNNING_MODAL'}

    def update_movement(self, context, dt):
        player = bpy.data.objects.get("Player_Root")
        camera = bpy.data.objects.get("Player_Camera_3rd")
        if not player or not camera:
            return

        # Direction calculation relative to camera yaw
        fwd = Vector((math.sin(self.cam_yaw), math.cos(self.cam_yaw), 0)).normalized()
        right = Vector((math.cos(self.cam_yaw), -math.sin(self.cam_yaw), 0)).normalized()

        move_dir = Vector((0.0, 0.0, 0.0))
        if self.keys['FORWARD']:
            move_dir += fwd
        if self.keys['BACKWARD']:
            move_dir -= fwd
        if self.keys['LEFT']:
            move_dir -= right
        if self.keys['RIGHT']:
            move_dir += right

        # Horizontal movement
        if move_dir.length_squared > 0.001:
            move_dir.normalize()
            speed = self.walk_speed * (self.sprint_mult if self.keys['SPRINT'] else 1.0)
            step = move_dir * speed * dt

            # Target position
            cand_pos = player.location + step
            if not check_collision(cand_pos):
                player.location.x = cand_pos.x
                player.location.y = cand_pos.y

            # Rotate player character towards movement direction
            player.rotation_euler.z = math.atan2(move_dir.x, move_dir.y)

        # Vertical movement (Gravity & Ground Detection)
        self.velocity_z -= self.gravity * dt
        player.location.z += self.velocity_z * dt

        # Ground height: Plinth elevation inside building, 0 outside
        ground_z = 0.0
        if -20.6 <= player.location.x <= 20.6 and -8.6 <= player.location.y <= 8.6:
            ground_z = 0.32
        elif -6.0 <= player.location.x <= 6.0 and 8.6 <= player.location.y <= 10.6:
            ground_z = 0.15

        if player.location.z <= ground_z:
            player.location.z = ground_z
            self.velocity_z = 0.0
            self.is_grounded = True

        # Smooth Camera Follow
        target_cam_pos = Vector((
            player.location.x - math.sin(self.cam_yaw) * self.cam_distance * math.cos(self.cam_pitch),
            player.location.y - math.cos(self.cam_yaw) * self.cam_distance * math.cos(self.cam_pitch),
            player.location.z + self.cam_height + math.sin(self.cam_pitch) * self.cam_distance
        ))

        # Lerp camera position
        camera.location = camera.location.lerp(target_cam_pos, 0.18)

        # Aim camera at student head/chest (z + 1.4)
        look_target = Vector((player.location.x, player.location.y, player.location.z + 1.4))
        cam_dir = (look_target - camera.location).normalized()
        rot_quat = cam_dir.to_track_quat('-Z', 'Y')
        camera.rotation_euler = rot_quat.to_euler()

        # Tag redraw for responsive viewport rendering
        if context.area:
            context.area.tag_redraw()

    def execute(self, context):
        build_student_character()
        self.last_time = time.time()
        self._timer = context.window_manager.event_timer_add(0.016, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, "[IMRD Game] Started! Controls: WASD = Move | Mouse = Look | Shift = Sprint | Space = Jump | Esc = Exit")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

# Registration
def register():
    bpy.utils.register_class(IMRD_OT_PlayerController)

def unregister():
    bpy.utils.unregister_class(IMRD_OT_PlayerController)

# Standalone execution (build character & render screenshot)
if __name__ == "__main__":
    register()

    # Load imrd_campus.blend if run standalone in background mode
    if BLEND_FILE.exists():
        bpy.ops.wm.open_mainfile(filepath=str(BLEND_FILE))

    root, cam = build_student_character()
    bpy.context.scene.camera = cam

    # Render a 3rd-person screenshot
    bpy.context.scene.render.filepath = str(PLAYER_RENDER)
    try:
        bpy.ops.render.render(write_still=True)
        print(f"[Player Controller] Third-person view rendered to: {PLAYER_RENDER}")
    except Exception as e:
        print(f"[Player Controller] Render warning: {e}")

    # Save updated blend file
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_FILE))
    print(f"[Player Controller] Successfully configured and saved to: {BLEND_FILE}")
