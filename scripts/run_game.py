"""
run_game.py
===========
Master Integration Entry Point for the IMRD 3D Game in Blender.
Combines:
- 01_build_campus.py (3D campus environment)
- 02_player_controller.py (Student avatar, 3rd person camera, physics & collision)
- 03_npc_interactions.py (Prof. Sharma, students, collectible ID card, interactive door)
- 04_missions.py (Data-driven missions, XP, leveling, exploration triggers)
- 05_game_ui.py (Real-time Viewport HUD overlay)

Supports:
- Interactive 3D Viewport gameplay via Blender modal operator and UI Sidebar Panel (N-Panel).
- Background validation and camera render exports.
"""

import sys
import bpy
import math
import time
from mathutils import Vector, Euler
from pathlib import Path

# Add scripts directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Import sub-modules
import importlib
missions_mod = importlib.import_module("04_missions")
MissionManager = missions_mod.MissionManager

interactions_mod = importlib.import_module("03_npc_interactions")
get_active_interaction = interactions_mod.get_active_interaction
setup_all_npcs_and_interactives = interactions_mod.setup_all_npcs_and_interactives

player_mod = importlib.import_module("02_player_controller")
build_student_character = player_mod.build_student_character
check_collision = player_mod.check_collision

ui_mod = importlib.import_module("05_game_ui")
GameHUD = ui_mod.GameHUD

# [INTRO INTEGRATION 1/4] optional cinematic intro (scripts/06_intro_cinematic.py)
try:
    intro_mod = importlib.import_module("06_intro_cinematic")
except Exception as _intro_exc:          # the game still runs without the intro
    intro_mod = None
    print(f"[Run Game] Intro cinematic unavailable: {_intro_exc!r}")

OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BLEND_FILE = OUTPUT_DIR / "imrd_campus.blend"
GAME_RENDER = OUTPUT_DIR / "gameplay_overview.png"

# Global Instances
g_mission_mgr = MissionManager()
g_hud = GameHUD()

# ----------------------------------------------------------------------
# MASTER MODAL OPERATOR: FULL GAMEPLAY LOOP
# ----------------------------------------------------------------------
class IMRD_OT_StartGame(bpy.types.Operator):
    """Start Playing the IMRD Campus Game in 3D Viewport"""
    bl_idname = "imrd.start_game"
    bl_label = "Play IMRD Campus Game"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    last_time = 0.0
    _running = False   # [INTRO INTEGRATION 2/4] only one game loop / HUD at a time

    # Controls state
    keys = {
        'FORWARD': False,
        'BACKWARD': False,
        'LEFT': False,
        'RIGHT': False,
        'SPRINT': False,
    }

    walk_speed = 6.2
    sprint_mult = 1.85
    jump_strength = 6.8
    gravity = 18.0
    velocity_z = 0.0
    is_grounded = True

    cam_distance = 5.2
    cam_height = 2.4
    cam_yaw = math.pi
    cam_pitch = 0.22

    active_interaction = None
    door_open = False

    def modal(self, context, event):
        # Exit on Esc or Q
        if event.type in {'ESC', 'Q'} and event.value == 'PRESS':
            self.cancel(context)
            self.report({'INFO'}, "[IMRD Game] Game stopped.")
            return {'CANCELLED'}

        # Movement Inputs
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

        # Interaction Input: E Key
        elif event.type == 'E' and event.value == 'PRESS':
            self.handle_interaction(context)

        # Mouse Look
        if event.type == 'MOUSEMOVE':
            dx = event.mouse_x - event.mouse_prev_x
            dy = event.mouse_y - event.mouse_prev_y
            self.cam_yaw -= dx * 0.004
            self.cam_pitch = max(-0.35, min(0.65, self.cam_pitch + dy * 0.003))

        # Main Update Tick
        if event.type == 'TIMER':
            now = time.time()
            dt = min(0.08, now - self.last_time) if self.last_time > 0 else 0.016
            self.last_time = now

            self.update_gameplay(context, dt)

        return {'RUNNING_MODAL'}

    def handle_interaction(self, context):
        if not self.active_interaction:
            return

        item = self.active_interaction
        item_id = item["id"]

        if item_id == "npc_guide":
            notifs = g_mission_mgr.on_talk_to_guide()
            for n in notifs:
                g_hud.post_notification(n)
            self.report({'INFO'}, item["dialogue"][0])

        elif item_id == "item_id_card":
            notifs = g_mission_mgr.on_pickup_id_card()
            for n in notifs:
                g_hud.post_notification(n)
            # Hide card mesh from scene
            card_obj = bpy.data.objects.get("Item_StudentIDCard")
            if card_obj:
                card_obj.hide_viewport = True
                card_obj.hide_render = True
            # Remove from interaction registry
            item["radius"] = 0.0

        elif item_id == "door_main":
            self.door_open = not self.door_open
            door_obj = bpy.data.objects.get("Interactive_Entrance_Door")
            if door_obj:
                door_obj.rotation_euler.z = math.radians(90 if self.door_open else 0)
            g_hud.post_notification(f"Door {'Opened' if self.door_open else 'Closed'}")

        elif item_id in ("npc_aarav", "npc_pooja"):
            g_hud.post_notification(item["dialogue"][0])
            self.report({'INFO'}, item["dialogue"][0])

        # Refresh HUD
        g_hud.set_objective(g_mission_mgr.get_current_objective_text())
        g_hud.set_stats(g_mission_mgr.level, g_mission_mgr.xp)

    def update_gameplay(self, context, dt):
        player = bpy.data.objects.get("Player_Root")
        camera = bpy.data.objects.get("Player_Camera_3rd")
        if not player or not camera:
            return

        # Move calculations
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

        if move_dir.length_squared > 0.001:
            move_dir.normalize()
            speed = self.walk_speed * (self.sprint_mult if self.keys['SPRINT'] else 1.0)
            step = move_dir * speed * dt

            cand_pos = player.location + step
            if not check_collision(cand_pos):
                player.location.x = cand_pos.x
                player.location.y = cand_pos.y

            player.rotation_euler.z = math.atan2(move_dir.x, move_dir.y)

        # Gravity & Elevation
        self.velocity_z -= self.gravity * dt
        player.location.z += self.velocity_z * dt

        ground_z = 0.0
        if -20.6 <= player.location.x <= 20.6 and -8.6 <= player.location.y <= 8.6:
            ground_z = 0.32
        elif -6.0 <= player.location.x <= 6.0 and 8.6 <= player.location.y <= 10.6:
            ground_z = 0.15

        if player.location.z <= ground_z:
            player.location.z = ground_z
            self.velocity_z = 0.0
            self.is_grounded = True

        # Camera follow
        target_cam_pos = Vector((
            player.location.x - math.sin(self.cam_yaw) * self.cam_distance * math.cos(self.cam_pitch),
            player.location.y - math.cos(self.cam_yaw) * self.cam_distance * math.cos(self.cam_pitch),
            player.location.z + self.cam_height + math.sin(self.cam_pitch) * self.cam_distance
        ))
        camera.location = camera.location.lerp(target_cam_pos, 0.20)
        look_target = Vector((player.location.x, player.location.y, player.location.z + 1.4))
        cam_dir = (look_target - camera.location).normalized()
        camera.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()

        # Exploration Triggers
        loc_notifs = g_mission_mgr.update_player_location(player.location)
        for notif in loc_notifs:
            g_hud.post_notification(notif)

        # Proximity Interaction Check
        self.active_interaction = get_active_interaction(player.location)
        if self.active_interaction:
            g_hud.set_interaction_prompt(self.active_interaction["prompt"])
        else:
            g_hud.set_interaction_prompt("")

        # Update HUD state
        g_hud.update_timer(dt)
        g_hud.set_objective(g_mission_mgr.get_current_objective_text())
        g_hud.set_stats(g_mission_mgr.level, g_mission_mgr.xp)

        if context.area:
            context.area.tag_redraw()

    def execute(self, context):
        # [INTRO INTEGRATION 3/4] never start a second loop (double HUD / double input)
        if IMRD_OT_StartGame._running:
            self.report({'WARNING'}, "[IMRD Game] Already running.")
            return {'CANCELLED'}
        IMRD_OT_StartGame._running = True
        # a previous session may have ended with keys still marked pressed
        for _k in self.keys:
            self.keys[_k] = False
        self.last_time = time.time()
        g_hud.register()
        self._timer = context.window_manager.event_timer_add(0.016, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, "[IMRD Game] Started! WASD to Move, Shift Sprint, Space Jump, E Interact, Esc Exit.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        IMRD_OT_StartGame._running = False
        g_hud.unregister()
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        # Auto-save progress
        g_mission_mgr.save_state()

# ----------------------------------------------------------------------
# BLENDER UI SIDEBAR PANEL (N-Panel under "IMRD Game")
# ----------------------------------------------------------------------
class IMRD_PT_GamePanel(bpy.types.Panel):
    bl_label = "IMRD 3D Campus Game"
    bl_idname = "IMRD_PT_GamePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IMRD Game"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.label(text="Campus Interactive Controls:", icon='GAME')
        col.operator("imrd.start_game", text="▶ Start Game (WASD)", icon='PLAY')

        layout.separator()
        box = layout.box()
        box.label(text="Active Mission:", icon='CHECKMARK')
        box.label(text=g_mission_mgr.get_current_objective_text())

        stats_row = layout.row(align=True)
        stats_row.label(text=f"Level: {g_mission_mgr.level}")
        stats_row.label(text=f"XP: {g_mission_mgr.xp}")

        layout.separator()
        col2 = layout.column(align=True)
        col2.label(text="Controls Reference:")
        col2.label(text="• WASD / Arrows : Walk")
        col2.label(text="• Shift : Sprint")
        col2.label(text="• Space : Jump")
        col2.label(text="• Mouse : Look around")
        col2.label(text="• E : Interact with NPCs/Items")
        col2.label(text="• Esc / Q : Exit to normal Blender")

# ----------------------------------------------------------------------
# REGISTRATION & SETUP
# ----------------------------------------------------------------------
classes = (
    IMRD_OT_StartGame,
    IMRD_PT_GamePanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    if intro_mod:
        intro_mod.register()

def unregister():
    if intro_mod:
        intro_mod.unregister()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

# Execution Entry Point
if __name__ == "__main__":
    register()

    # Load campus if available
    if BLEND_FILE.exists():
        bpy.ops.wm.open_mainfile(filepath=str(BLEND_FILE))

    # Ensure player and NPCs are populated
    build_student_character()
    setup_all_npcs_and_interactives()

    # Position Camera for gameplay showcase render
    player = bpy.data.objects.get("Player_Root")
    cam = bpy.data.objects.get("Player_Camera_3rd")
    if player and cam:
        cam.location = (0, 73.5, 2.4)
        cam.rotation_euler = Euler((math.radians(78), 0, math.radians(180)), 'XYZ')
        bpy.context.scene.camera = cam

    # Render gameplay perspective screenshot
    bpy.context.scene.render.filepath = str(GAME_RENDER)
    try:
        bpy.ops.render.render(write_still=True)
        print(f"[Run Game] Rendered gameplay showcase to: {GAME_RENDER}")
    except Exception as e:
        print(f"[Run Game] Render note: {e}")

    # Save final blend file
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_FILE))
    print(f"\n[Run Game] Integration Complete! Master scene saved to: {BLEND_FILE}")
    print("[Run Game] To play interactively in Blender, run:")
    print(f'  blender "{BLEND_FILE}" --python "{SCRIPT_DIR / "run_game.py"}"')
    print("  Then press 'N' in the 3D Viewport -> 'IMRD Game' tab -> 'Start Game' (or press Spacebar / Operator search).\n")

    # [INTRO INTEGRATION 4/4] play the cinematic intro in the interactive UI (skip with: -- --no-intro)
    if intro_mod and not bpy.app.background and "--no-intro" not in sys.argv:
        intro_mod.request_play(1.0)
