"""
05_game_ui.py
=============
Real-time 2D Viewport HUD Overlay for modern Blender (4.x / 5.x) using blf & gpu.
Renders:
- Top Header: Campus Game Title.
- Mission Banner: Current objective and progress.
- Status HUD: Level, XP, and speed indicator.
- Action Prompt: Proximity interact notifications ([E] Talk / Pick up).
- Controls Guide: Keybindings reference bar.
"""

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

class GameHUD:
    def __init__(self):
        self.font_id = 0
        self.handler = None
        self.active_prompt = ""
        self.objective_text = "MISSION: First Day at IMRD - Talk to Prof. Sharma at Entrance Plaza"
        self.level = 1
        self.xp = 0
        self.recent_notif = ""
        self.notif_timer = 0.0

    def set_interaction_prompt(self, text):
        self.active_prompt = text

    def set_objective(self, text):
        self.objective_text = text

    def set_stats(self, level, xp):
        self.level = level
        self.xp = xp

    def post_notification(self, text):
        self.recent_notif = text
        self.notif_timer = 5.0 # seconds

    def update_timer(self, dt):
        if self.notif_timer > 0:
            self.notif_timer -= dt
            if self.notif_timer <= 0:
                self.recent_notif = ""

    def draw_2d(self):
        """Called inside Blender's POST_PIXEL draw callback."""
        region = bpy.context.region
        if not region:
            return

        w, h = region.width, region.height
        font_id = self.font_id

        # 1. TOP TITLE BAR
        blf.size(font_id, 18)
        blf.color(font_id, 0.95, 0.95, 0.95, 1.0)
        blf.position(font_id, 24, h - 34, 0)
        blf.draw(font_id, "RCPET IMRD SHIRPUR  -  3D Virtual Campus")

        # 2. PLAYER STATS (Top Right)
        stats_text = f"Level: {self.level}   |   XP: {self.xp}"
        blf.size(font_id, 16)
        blf.color(font_id, 0.3, 0.85, 1.0, 1.0)
        dim_x, _ = blf.dimensions(font_id, stats_text)
        blf.position(font_id, w - dim_x - 24, h - 34, 0)
        blf.draw(font_id, stats_text)

        # 3. ACTIVE MISSION BANNER (Top Center)
        if self.objective_text:
            blf.size(font_id, 15)
            blf.color(font_id, 1.0, 0.85, 0.25, 1.0)
            obj_w, _ = blf.dimensions(font_id, self.objective_text)
            blf.position(font_id, max(24, (w - obj_w) / 2), h - 70, 0)
            blf.draw(font_id, self.objective_text)

        # 4. RECENT TOAST NOTIFICATION (Center-high)
        if self.recent_notif and self.notif_timer > 0:
            blf.size(font_id, 16)
            blf.color(font_id, 0.35, 1.0, 0.45, 1.0)
            notif_w, _ = blf.dimensions(font_id, self.recent_notif)
            blf.position(font_id, (w - notif_w) / 2, h - 110, 0)
            blf.draw(font_id, f"★  {self.recent_notif}")

        # 5. INTERACTION PROMPT (Bottom Center)
        if self.active_prompt:
            blf.size(font_id, 20)
            blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
            p_w, _ = blf.dimensions(font_id, self.active_prompt)
            blf.position(font_id, (w - p_w) / 2, 85, 0)
            blf.draw(font_id, f"[ {self.active_prompt} ]")

        # 6. CONTROLS GUIDE (Bottom Center-low)
        controls_str = "WASD: Move   |   Shift: Sprint   |   Space: Jump   |   E: Interact   |   Esc: Exit"
        blf.size(font_id, 13)
        blf.color(font_id, 0.75, 0.75, 0.75, 0.85)
        c_w, _ = blf.dimensions(font_id, controls_str)
        blf.position(font_id, (w - c_w) / 2, 28, 0)
        blf.draw(font_id, controls_str)

    def register(self):
        if self.handler is None:
            self.handler = bpy.types.SpaceView3D.draw_handler_add(
                self.draw_2d, (), 'WINDOW', 'POST_PIXEL'
            )

    def unregister(self):
        if self.handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handler, 'WINDOW')
            self.handler = None
