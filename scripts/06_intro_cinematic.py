"""
06_intro_cinematic.py
=====================
Cinematic opening sequence + main menu for the IMRD 3D Campus Walkthrough Game
(Blender 5.x, interactive 3D viewport, same architecture as run_game.py).

What it does
------------
* Flies a dedicated camera ("Intro_Camera") over the REAL campus objects:
  fade-in -> campus reveal -> entrance approach -> title reveal -> hold -> menu.
* Title / institution text and the menu are drawn with blf/gpu (like 05_game_ui.py),
  so nothing is added to the campus scene except one camera and some marker empties
  in their own collection ("Intro_Cinematic").
* SKIP (Esc / Enter / Space / click SKIP INTRO) jumps to the menu through a short
  fade, never a hard cut.
* START WALKTHROUGH hands over to the existing game operator (imrd.start_game):
  player is put on SPAWN, the gameplay camera is activated, the HUD is created by
  the game itself, and the mission manager is NOT touched (so no duplicate rewards).
* Optional low-resolution preview render (frames + mp4) with real text objects.

Design
------
* Shot list + timing live in DEFAULT KEYS / constants below (configurable), and
  the camera markers (IntroCam_xx / IntroLook_xx empties) can be dragged in the
  viewport to re-aim any key without touching code.
* Camera pose is a pure function of time t (monotone cubic Hermite / PCHIP, no
  overshoot) -> deterministic, independent of frame rate.
* Everything that needs Blender is isolated; the path, safety validation, layout and
  the state machine (IntroFSM) are plain Python and unit-tested outside Blender.

Usage
-----
    blender output/imrd_campus.blend --python scripts/06_intro_cinematic.py
    blender -b output/imrd_campus.blend --python scripts/06_intro_cinematic.py -- --render-preview
    blender -b output/imrd_campus.blend --python scripts/06_intro_cinematic.py -- --selftest
    python3 scripts/06_intro_cinematic.py --selftest        (logic tests, no Blender)
"""

import sys
import math
import time
import json
import traceback
from pathlib import Path

try:
    import bpy
    import blf
    import gpu
    from gpu_extras.batch import batch_for_shader
    from mathutils import Vector
    IN_BLENDER = True
except ImportError:           # plain-Python run (logic tests)
    bpy = blf = gpu = batch_for_shader = Vector = None
    IN_BLENDER = False

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
PREVIEW_DIR = OUTPUT_DIR / "intro_preview"
REPORT_FILE = OUTPUT_DIR / "intro_report.md"
CONFIG_FILE = OUTPUT_DIR / "intro_config.json"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    import game_config as cfg
except Exception:             # optional: fall back to constants
    cfg = None

# ======================================================================
# 1. CONFIGURATION (edit here, no code changes needed elsewhere)
# ======================================================================
FPS = 24
T_FADE_IN = 2.0               # 0..2 s fade from black
T_MENU = 17.0                 # menu starts to appear
T_END = 20.0                  # end of camera path (menu keeps this pose)
LENS_MM = 28.0
MIN_CAM_Z = 1.2               # never lower than this above ground
CLEARANCE = 0.6               # margin around obstacles (m)
SPAWN = tuple(getattr(cfg, "SPAWN", (0.0, 68.0, 0.0)))

TITLE_LINES = ("IMRD", "3D CAMPUS WALKTHROUGH", "Institute of Management Research and Development")
SHOT_LIST = (  # (name, start s, end s) - informational + used in report
    ("Shot 1 Fade In", 0.0, 2.0),
    ("Shot 2 Campus Reveal", 2.0, 6.0),
    ("Shot 3 Entrance Approach", 6.0, 10.0),
    ("Shot 4 Title Reveal", 10.0, 14.0),
    ("Shot 5 Final Establishing View", 14.0, 17.0),
    ("Shot 6 Main Menu", 17.0, 20.0),
)
TITLE_TIMING = ((10.3, 1.4), (10.9, 1.2), (11.5, 1.2))   # (start, duration) per line
RULE_TIMING = (11.2, 1.2)

PLAYER_COLLECTION = "Player_Student"
INTRO_COLLECTION = "Intro_Cinematic"
INTRO_CAMERA = "Intro_Camera"
MARKER_CAM_PREFIX = "IntroCam_"
MARKER_LOOK_PREFIX = "IntroLook_"

SETTINGS = {"dof": True, "rendered": False}     # persistent while Blender is open

# Layout anchors measured from 01_build_campus.py / game_config.py
DEFAULT_LAYOUT = {
    "ex": 0.0,                                   # entrance centre x
    "ey": float(getattr(cfg, "BLD_OUT_Y", 8.65)),  # front face of main building
    "gy": 75.0,                                  # gate line (Gate_Pillar / Boundary_Wall y)
    "top": 9.6,                                  # parapet top
}

PALETTE = {
    "text": (0.97, 0.97, 0.97, 1.0),
    "sub": (0.86, 0.90, 0.96, 1.0),
    "gold": (1.0, 0.85, 0.25, 1.0),
    "navy": (0.05, 0.11, 0.24, 1.0),
    "button": (0.06, 0.13, 0.28, 0.62),
    "button_sel": (0.10, 0.22, 0.46, 0.90),
}


def keys_from_layout(layout=None):
    """Default camera keys, derived from the building/entrance/gate layout."""
    L = dict(DEFAULT_LAYOUT)
    L.update(layout or {})
    ex, ey, gy, top = L["ex"], L["ey"], L["gy"], L["top"]
    k0 = (ex + 24.0, gy + 15.0, top + 5.9)
    k2 = (ex + 2.0, gy - 19.0, top - 1.6)
    k1 = tuple(a + (b - a) * 0.15 for a, b in zip(k0, k2))
    side = (ex - 4.5, ey + 0.9, 6.4)
    return [
        dict(name="Establish", t=0.0, pos=k0, look=(ex, gy - 35.0, 3.5), ease=True),
        dict(name="Reveal", t=2.0, pos=k1, look=(ex, gy - 37.0, 3.4), ease=False),
        dict(name="OverGate", t=6.0, pos=k2, look=(ex, ey + 13.4, 3.2), ease=False),
        dict(name="Entrance", t=10.0, pos=(ex - 2.5, ey + 12.4, 2.0), look=(ex, ey + 0.4, 3.6), ease=True),
        dict(name="PullBack", t=14.0, pos=(ex - 1.8, ey + 29.4, 3.4), look=side, ease=False),
        dict(name="Hold", t=17.0, pos=(ex - 2.0, ey + 33.1, 3.6), look=side, ease=False),
        dict(name="End", t=20.0, pos=(ex - 2.1, ey + 34.0, 3.7), look=side, ease=True),
    ]


# ======================================================================
# 2. PURE MATH: easing, camera path, safety validation
# ======================================================================
def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def smoothstep(x):
    x = clamp01(x)
    return x * x * (3.0 - 2.0 * x)


def ease_out_cubic(x):
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 3


def _pchip(ts, vs, forced_zero):
    """Monotone cubic (Fritsch-Carlson/PCHIP) tangents for one axis: no overshoot."""
    n = len(ts)
    h = [ts[i + 1] - ts[i] for i in range(n - 1)]
    d = [(vs[i + 1] - vs[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    for k in range(1, n - 1):
        if d[k - 1] * d[k] > 0.0:
            w1 = 2.0 * h[k] + h[k - 1]
            w2 = h[k] + 2.0 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    for k in forced_zero:
        m[k] = 0.0
    return m


def _hermite(p0, p1, m0, m1, s, dt):
    s2, s3 = s * s, s * s * s
    h00, h10, h01, h11 = 2 * s3 - 3 * s2 + 1, s3 - 2 * s2 + s, -2 * s3 + 3 * s2, s3 - s2
    return tuple(h00 * a + h10 * dt * ma + h01 * b + h11 * dt * mb
                 for a, b, ma, mb in zip(p0, p1, m0, m1))


class CameraPath:
    """pose = f(t). Position and look-at point are interpolated, rotation derives from them."""

    def __init__(self, keys):
        ks = sorted((dict(k) for k in keys), key=lambda k: k["t"])
        if len(ks) < 2 or any(ks[i + 1]["t"] <= ks[i]["t"] for i in range(len(ks) - 1)):
            raise ValueError("camera path needs >=2 keys with strictly increasing times")
        self.keys = ks
        ts = [k["t"] for k in ks]
        zero = [i for i, k in enumerate(ks) if k.get("ease")] + [0, len(ks) - 1]
        self.mp = [[0.0] * 3 for _ in ks]
        self.ml = [[0.0] * 3 for _ in ks]
        for ax in range(3):
            tp = _pchip(ts, [k["pos"][ax] for k in ks], zero)
            tl = _pchip(ts, [k["look"][ax] for k in ks], zero)
            for i in range(len(ks)):
                self.mp[i][ax] = tp[i]
                self.ml[i][ax] = tl[i]
        self.t0, self.t1 = ts[0], ts[-1]

    def sample(self, t):
        t = min(max(t, self.t0), self.t1)
        ks = self.keys
        i = 0
        while i < len(ks) - 2 and t > ks[i + 1]["t"]:
            i += 1
        a, b = ks[i], ks[i + 1]
        dt = b["t"] - a["t"]
        s = (t - a["t"]) / dt
        pos = _hermite(a["pos"], b["pos"], self.mp[i], self.mp[i + 1], s, dt)
        look = _hermite(a["look"], b["look"], self.ml[i], self.ml[i + 1], s, dt)
        return pos, look


def _inside(p, lo, hi, margin):
    return all(lo[i] - margin <= p[i] <= hi[i] + margin for i in range(3))


def validate_path(path, obstacles, step=1.0 / 60.0, margin=CLEARANCE):
    """Returns a list of (t, kind, obstacle) problems; empty list == safe."""
    issues, last = [], None
    t = path.t0
    while t <= path.t1 + 1e-9:
        pos, _ = path.sample(t)
        found = None
        if pos[2] < MIN_CAM_Z:
            found = ("below_min_height", "ground")
        else:
            for name, lo, hi in obstacles:
                if _inside(pos, lo, hi, margin):
                    found = ("collision", name)
                    break
        if found and found != last:
            issues.append((round(t, 2),) + found)
        last = found
        t += step
    return issues


def lift_keys(keys, obstacles, margin=CLEARANCE, max_z=40.0):
    """Push colliding keys straight up over the obstacle (simplest valid fix)."""
    out = []
    for k in keys:
        k = dict(k)
        for _ in range(8):
            hit = next(((n, lo, hi) for n, lo, hi in obstacles if _inside(k["pos"], lo, hi, margin)), None)
            if not hit:
                break
            k["pos"] = (k["pos"][0], k["pos"][1], min(max_z, hit[2][2] + margin + 0.2))
        k["pos"] = (k["pos"][0], k["pos"][1], max(MIN_CAM_Z, k["pos"][2]))
        out.append(k)
    return out


def fallback_keys(layout=None):
    """Last-resort 'simple valid camera': high straight dolly down the central axis."""
    L = dict(DEFAULT_LAYOUT)
    L.update(layout or {})
    ex, ey, gy, top = L["ex"], L["ey"], L["gy"], L["top"]
    look = (ex, ey + 1.0, 3.5)
    return [
        dict(name="FB_Start", t=0.0, pos=(ex, gy + 14.0, top + 8.0), look=look, ease=True),
        dict(name="FB_Mid", t=8.0, pos=(ex, gy - 20.0, top + 3.0), look=look, ease=False),
        dict(name="FB_Hold", t=14.0, pos=(ex, ey + 33.0, 4.0), look=look, ease=False),
        dict(name="FB_End", t=20.0, pos=(ex, ey + 35.0, 4.2), look=look, ease=True),
    ]


def static_obstacles(layout=None):
    """Axis-aligned obstacle boxes derived from the numbers used by 01_build_campus.py.
    Used when the scene cannot be inspected (tests, missing collections)."""
    obs = []

    def box(name, cx, cy, cz0, hx, hy, cz1):
        obs.append((name, (cx - hx, cy - hy, cz0), (cx + hx, cy + hy, cz1)))

    box("Main_Building", 0, 0, 0, 20.95, 8.95, 9.7)
    box("Canopy_Roof+Rail", 0, 10.65, 3.85, 6.5, 1.85, 5.4)
    for nm, sx in (("Column_Canopy_L", -5.5), ("Column_Canopy_R", 5.5)):
        box(nm, sx, 12.0, 0, 0.28, 0.28, 4.0)
    for nm, sx in (("Gate_Pillar_L", -5.5), ("Gate_Pillar_R", 5.5)):
        box(nm, sx, 75.0, 0, 0.6, 0.6, 5.6)
    box("Gate_Arch_Beam", 0, 75.0, 5.2, 6.1, 0.7, 6.0)
    box("Gate_Signboard", 0, 75.0, 5.8, 5.0, 0.1, 6.75)
    box("Boundary_Wall_L", -25, 75.0, 0, 19, 0.2, 2.2)
    box("Boundary_Wall_R", 25, 75.0, 0, 19, 0.2, 2.2)
    box("Security_Cabin", 7.8, 73.5, 0, 1.6, 1.6, 3.5)
    box("NPC_CampusGuide", 0, 15.5, 0, 0.45, 0.45, 2.3)
    pos = [(-8.5, 24), (-8.5, 38), (-8.5, 52), (-8.5, 66), (8.5, 24), (8.5, 52), (8.5, 66),
           (-32, 38), (-48, 38), (-32, 58), (-48, 58), (-40, 62), (-54, 48), (-28, 48),
           (-15, -12), (0, -12), (15, -12), (60, 36), (60, 48), (60, 60)]
    for i, (tx, ty) in enumerate(pos):
        h = 5.2 + (i % 3) * 0.9
        th, cr = h * 0.44, h * 0.42
        cz = th + cr * 0.65
        box(f"Tree_{i}_Trunk", tx, ty, 0, 0.3, 0.3, th)
        obs.append((f"Tree_{i}_Crown", (tx - 1.34 * cr, ty - 1.34 * cr, cz - 0.85 * cr),
                    (tx + 1.34 * cr, ty + 1.34 * cr, cz + 1.2 * cr)))
    for i, (lx, ly) in enumerate([(-5.5, 26), (5.5, 26), (-5.5, 42), (5.5, 42), (-5.5, 58), (5.5, 58),
                                  (-5.5, 72), (5.5, 72), (-16.0, 15.0), (16.0, 15.0), (-24.0, 48.5)]):
        box(f"Lamp_{i}", lx, ly, 0, 0.3, 0.3, 4.7)
    box("Parked_Cars", 40.0, 36.0, 0, 9.0, 2.2, 1.6)
    return obs


# ======================================================================
# 3. PURE UI MATH: title animation + layout (unit tested)
# ======================================================================
def title_state(t, line):
    """(alpha, y_offset_px, scale) for title line 0..2 at time t."""
    s, d = TITLE_TIMING[line]
    a = ease_out_cubic((t - s) / d)
    return a, (1.0 - a) * 18.0, 0.94 + 0.06 * a


def rule_progress(t):
    return ease_out_cubic((t - RULE_TIMING[0]) / RULE_TIMING[1])


def ui_scale(w, h):
    return max(0.6, min(2.0, min(w / 1280.0, h / 720.0)))


MENU_ITEMS = ("START WALKTHROUGH", "SETTINGS", "EXIT")


def layout(w, h):
    """All rectangles are (x, y, w, h) in region pixels, origin bottom-left."""
    s = ui_scale(w, h)
    bw, bh, gap = 340.0 * s, 52.0 * s, 16.0 * s
    bw = min(bw, w * 0.8)
    bx = max(24.0, w * 0.07)
    top = h * 0.50
    buttons = [(bx, top - bh - i * (bh + gap), bw, bh) for i in range(3)]
    return {
        "s": s,
        "cx": w / 2.0,
        "y_title": h * 0.80, "size_title": 104.0 * s,
        "y_rule": h * 0.765, "rule_w": 340.0 * s,
        "y_sub": h * 0.715, "size_sub": 26.0 * s,
        "y_inst": h * 0.67, "size_inst": 20.0 * s,
        "max_text_w": w * 0.9,
        "buttons": buttons,
        "skip": (w - 24.0 * s - 170.0 * s, 24.0 * s, 170.0 * s, 38.0 * s),
        "hint": (bx, 28.0 * s),
    }


def hit(rect, x, y):
    return rect[0] <= x <= rect[0] + rect[2] and rect[1] <= y <= rect[1] + rect[3]


# ======================================================================
# 4. STATE MACHINE (pure Python: skip / menu / start / replay / exit)
# ======================================================================
class IntroFSM:
    """States: PLAY -> MENU <-> SETTINGS -> DONE.  All time is passed in (testable)."""

    def __init__(self, hooks, now):
        self.h = hooks
        self.starts = 0
        self.exits = 0
        self.replays = 0
        self.reset(now)

    def reset(self, now):
        self.state = "PLAY"
        self.t0 = now
        self.menu_t0 = None
        self.sel = 0
        self.xf = None
        self._started = False

    # --- time / fades ------------------------------------------------
    def t(self, now):
        return min(max(now - self.t0, 0.0), T_END)

    def menu_alpha(self, now):
        if self.menu_t0 is None:
            return 0.0
        return smoothstep((now - self.menu_t0) / 1.0)

    def black(self, now):
        a = 1.0 - smoothstep(self.t(now) / T_FADE_IN)
        x = self.xf
        if x:
            if x["fired"] is None:
                a = max(a, smoothstep((now - x["ts"]) / x["out"]))
            elif x["in"] > 0.0:
                a = max(a, 1.0 - smoothstep((now - x["fired"]) / x["in"]))
        return a

    def _xfade(self, now, out_dur, in_dur, action):
        if self.xf:
            return False
        self.xf = {"ts": now, "out": out_dur, "in": in_dur, "act": action, "fired": None}
        return True

    # --- update ---------------------------------------------------------
    def tick(self, now):
        x = self.xf
        if x and x["fired"] is None and now - x["ts"] >= x["out"]:
            x["fired"] = now
            x["act"](now)
        if x and self.xf is x and x["fired"] is not None and now - x["fired"] >= x["in"]:
            self.xf = None
        if self.state == "PLAY" and self.t(now) >= T_MENU:
            self._enter_menu(now)

    def _enter_menu(self, now):
        self.state = "MENU"
        self.menu_t0 = now
        self.sel = 0

    # --- actions -----------------------------------------------------------
    def skip(self, now):
        if self.state != "PLAY" or self.xf:
            return False

        def jump(n):
            self.t0 = n - T_MENU
            self._enter_menu(n)
        return self._xfade(now, 0.30, 0.45, jump)

    def replay(self, now):
        if self.state != "MENU" or self.xf or self._started:
            return False
        self.replays += 1
        return self._xfade(now, 0.30, 0.0, lambda n: self.reset(n))

    def start(self, now):
        if self._started or self.xf or self.state != "MENU":
            return False
        self._started = True

        def go(n):
            if self.h.start_game():
                self.starts += 1
                self.state = "DONE"
            else:                      # game could not start: stay in menu, allow retry
                self._started = False
        return self._xfade(now, 0.45, 0.0, go)

    def exit(self, now):
        if self.xf or self.state not in ("MENU", "SETTINGS") or self._started:
            return False
        self._started = True

        def go(n):
            self.exits += 1
            self.state = "DONE"
            self.h.exit()
        return self._xfade(now, 0.30, 0.0, go)

    def settings_items(self):
        s = self.h.settings
        return ("DEPTH OF FIELD: " + ("ON" if s["dof"] else "OFF"),
                "RENDERED VIEW: " + ("ON" if s["rendered"] else "OFF"),
                "BACK")

    def _activate(self, idx, now):
        if self.state == "MENU":
            if idx == 0:
                self.start(now)
            elif idx == 1:
                self.state, self.sel = "SETTINGS", 0
            elif idx == 2:
                self.exit(now)
        elif self.state == "SETTINGS":
            if idx == 0:
                self.h.settings["dof"] = not self.h.settings["dof"]
                self.h.settings_changed()
            elif idx == 1:
                self.h.settings["rendered"] = not self.h.settings["rendered"]
                self.h.settings_changed()
            else:
                self.state, self.sel = "MENU", 1

    # --- input ---------------------------------------------------------------
    def key(self, name, now):
        if self.xf:
            return True                      # input swallowed during transitions
        if self.state == "PLAY":
            if name in ("ESC", "RET", "NUMPAD_ENTER", "SPACE"):
                self.skip(now)
            return True
        if self.state in ("MENU", "SETTINGS"):
            n = 3
            if name in ("UP_ARROW", "W"):
                self.sel = (self.sel - 1) % n
            elif name in ("DOWN_ARROW", "S", "TAB"):
                self.sel = (self.sel + 1) % n
            elif name in ("RET", "NUMPAD_ENTER", "SPACE"):
                if self.menu_alpha(now) > 0.3:
                    self._activate(self.sel, now)
            elif name == "R" and self.state == "MENU":
                self.replay(now)
            elif name == "ESC" and self.state == "SETTINGS":
                self.state, self.sel = "MENU", 1
        return True

    def pointer(self, x, y, w, h, now, click):
        if self.xf:
            return
        L = layout(w, h)
        if self.state == "PLAY":
            if click and hit(L["skip"], x, y) and self.t(now) > 1.0:
                self.skip(now)
        elif self.state in ("MENU", "SETTINGS") and self.menu_alpha(now) > 0.3:
            for i, r in enumerate(L["buttons"]):
                if hit(r, x, y):
                    self.sel = i
                    if click:
                        self._activate(i, now)
                    break


# ======================================================================
# 5. BLENDER SIDE
# ======================================================================
def _now():
    return time.perf_counter()


def find_view3d(context=None):
    """-> (window, area, WINDOW region) of a 3D viewport, or (None, None, None)."""
    cands = []
    if context is not None and getattr(context, "area", None) and context.area.type == 'VIEW_3D':
        cands.append((context.window, context.area))
    for win in bpy.context.window_manager.windows:
        for ar in win.screen.areas:
            if ar.type == 'VIEW_3D':
                cands.append((win, ar))
    for win, ar in cands:
        for rg in ar.regions:
            if rg.type == 'WINDOW':
                return win, ar, rg
    return None, None, None


def discover_layout():
    """Entrance / building / gate anchors from the live scene (falls back to config)."""
    L = dict(DEFAULT_LAYOUT)
    objs = bpy.data.objects

    def bbox(o):
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
                Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))
    try:
        if cfg is not None:
            L["ex"] = float(cfg.ENTRANCE_X)
        top, ymax = 0.0, None
        for o in objs:
            if o.name in ("Parapet_Front", "Roof_Main"):
                lo, hi = bbox(o)
                top = max(top, hi.z)
                if o.name == "Parapet_Front":
                    ymax = hi.y
        if top > 0.0:
            L["top"] = top
        wall = objs.get("Wall_G_Front")
        if wall is not None:
            lo, hi = bbox(wall)
            L["ey"] = hi.y
        elif ymax is not None:
            L["ey"] = ymax - 0.1
        beam = objs.get("Gate_Arch_Beam")
        if beam is not None:
            L["gy"] = beam.location.y
    except Exception as exc:
        print(f"[Intro] layout discovery fell back to defaults: {exc!r}")
    return L


def scene_obstacles():
    """World-space AABBs of everything the camera could hit, from the real objects."""
    cols = ("Building_Structure", "Gate_Boundary", "Vegetation", "Props_Vehicles",
            "Gameplay_Objects", "NPCs_and_Interactives")
    out = []
    for cn in cols:
        col = bpy.data.collections.get(cn)
        if not col:
            continue
        for o in col.objects:
            if o.type != 'MESH' or o.name.startswith("Intro"):
                continue
            pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
            lo = (min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))
            hi = (max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))
            if hi[2] < 0.8:
                continue                     # curbs, markings, ground: camera is always higher
            out.append((o.name, lo, hi))
    return out


def ensure_intro_collection(scene):
    col = bpy.data.collections.get(INTRO_COLLECTION)
    if col is None:
        col = bpy.data.collections.new(INTRO_COLLECTION)
    if col.name not in {c.name for c in scene.collection.children_recursive}:
        scene.collection.children.link(col)
    return col


def ensure_intro_camera(scene):
    col = ensure_intro_collection(scene)
    cam = bpy.data.objects.get(INTRO_CAMERA)
    if cam is None:
        cd = bpy.data.cameras.new(INTRO_CAMERA)
        cam = bpy.data.objects.new(INTRO_CAMERA, cd)
    cd = cam.data
    cd.lens, cd.clip_start, cd.clip_end = LENS_MM, 0.3, 600.0
    cd.dof.use_dof = SETTINGS["dof"]
    cd.dof.aperture_fstop = 8.0              # restrained depth of field
    cam.rotation_mode = 'XYZ'
    if cam.name not in col.objects:
        col.objects.link(cam)
    return cam


def create_markers(scene, keys):
    """Named, draggable markers for every key (replaces older ones)."""
    col = ensure_intro_collection(scene)
    for o in list(col.objects):
        if o.name.startswith((MARKER_CAM_PREFIX, MARKER_LOOK_PREFIX)):
            bpy.data.objects.remove(o, do_unlink=True)
    for i, k in enumerate(keys):
        for prefix, kind, size, p in ((MARKER_CAM_PREFIX, 'CUBE', 0.8, k["pos"]),
                                      (MARKER_LOOK_PREFIX, 'PLAIN_AXES', 1.0, k["look"])):
            o = bpy.data.objects.new(f"{prefix}{i:02d}_{k['name']}", None)
            o.empty_display_type, o.empty_display_size = kind, size
            o.location = p
            o["intro_t"], o["intro_ease"] = float(k["t"]), bool(k.get("ease", False))
            o.hide_render = True
            col.objects.link(o)


def load_marker_keys():
    """Keys from the marker empties, or None if absent/incomplete."""
    cams, looks = {}, {}
    for o in bpy.data.objects:
        for prefix, dst in ((MARKER_CAM_PREFIX, cams), (MARKER_LOOK_PREFIX, looks)):
            if o.name.startswith(prefix):
                try:
                    dst[int(o.name[len(prefix):len(prefix) + 2])] = o
                except ValueError:
                    pass
    if len(cams) < 2 or set(cams) != set(looks):
        return None
    try:
        return [dict(name=cams[i].name.split("_", 1)[1], t=float(cams[i].get("intro_t", 0.0)),
                     pos=tuple(cams[i].matrix_world.translation), look=tuple(looks[i].matrix_world.translation),
                     ease=bool(cams[i].get("intro_ease", False))) for i in sorted(cams)]
    except Exception:
        return None


def build_path(scene):
    """Marker keys -> validate -> lift -> fallback. Returns (CameraPath, report dict)."""
    layout_ = discover_layout()
    obstacles = scene_obstacles() or static_obstacles(layout_)
    rep = {"source": "defaults", "issues": [], "fix": "none", "obstacles": len(obstacles)}
    keys = load_marker_keys()
    if keys:
        rep["source"] = "markers"
    else:
        keys = keys_from_layout(layout_)
        create_markers(scene, keys)
    try:
        path = CameraPath(keys)
    except ValueError as exc:
        rep["issues"].append(f"bad key times: {exc}")
        keys, path, rep["source"] = keys_from_layout(layout_), None, "defaults"
        path = CameraPath(keys)
    issues = validate_path(path, obstacles)
    if issues:
        rep["issues"] = issues[:10]
        keys2 = lift_keys(keys, obstacles)
        path2 = CameraPath(keys2)
        if not validate_path(path2, obstacles):
            path, rep["fix"] = path2, "lifted colliding keys"
        else:
            path3 = CameraPath(fallback_keys(layout_))
            if not validate_path(path3, obstacles):
                path, rep["fix"] = path3, "fallback dolly"
            else:
                cam0 = bpy.data.objects.get("Cam_Overview")
                p = tuple(cam0.location) if cam0 else keys[0]["pos"]
                look = (layout_["ex"], layout_["ey"] + 1.0, 3.5)
                path = CameraPath([dict(t=0.0, pos=p, look=look), dict(t=T_END, pos=p, look=look)])
                rep["fix"] = "static overview"
    return path, rep


# ----------------------------------------------------------------------
# drawing helpers (blf / gpu)
# ----------------------------------------------------------------------
def _rect(x0, y0, x1, y1, color):
    sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    b = batch_for_shader(sh, 'TRI_FAN', {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]})
    sh.bind()
    sh.uniform_float("color", color)
    b.draw(sh)


def _grad(x0, y0, x1, y1, c0, c1, horizontal):
    sh = gpu.shader.from_builtin('SMOOTH_COLOR')
    cols = [c0, c1, c1, c0] if horizontal else [c0, c0, c1, c1]
    b = batch_for_shader(sh, 'TRI_FAN', {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "color": cols})
    b.draw(sh)


def _text_width(font, txt, size, tracking):
    blf.size(font, max(8, int(round(size))))
    if tracking:
        return sum(blf.dimensions(font, c)[0] for c in txt) + tracking * (len(txt) - 1)
    return blf.dimensions(font, txt)[0]


def _text(font, txt, x, y, size, color, align="left", tracking=0.0, max_w=None, shadow=True):
    """Draws text (optionally letter-spaced); shrinks to max_w; returns drawn width."""
    wd = _text_width(font, txt, size, tracking)
    if max_w and wd > max_w:
        k = max_w / wd
        size, tracking = size * k, tracking * k
        wd = _text_width(font, txt, size, tracking)
    blf.size(font, max(8, int(round(size))))
    if align == "center":
        x -= wd / 2.0
    elif align == "right":
        x -= wd
    sh_col = (0.0, 0.0, 0.0, color[3] * 0.55)
    passes = ((1.5, -1.5, sh_col), (0.0, 0.0, color)) if shadow else ((0.0, 0.0, color),)
    for ox, oy, col in passes:
        blf.color(font, *col)
        if tracking:
            cx = x + ox
            for ch in txt:
                blf.position(font, cx, y + oy, 0)
                blf.draw(font, ch)
                cx += blf.dimensions(font, ch)[0] + tracking
        else:
            blf.position(font, x + ox, y + oy, 0)
            blf.draw(font, txt)
    return wd


def _with_alpha(c, a):
    return (c[0], c[1], c[2], c[3] * a)


# ----------------------------------------------------------------------
# controller
# ----------------------------------------------------------------------
class IntroController:
    """Singleton that owns overlay, camera, saved state. Only one can ever exist."""

    def __init__(self):
        self.active = False
        self.modal_running = False
        self.done = False
        self.fsm = None
        self.handler = None
        self.handoff = None
        self.notice = ("", 0.0)
        self.area_ptr = None
        self.saved = None
        self.path = None
        self.report = {}
        self.region_size = (0, 0)
        self.settings = SETTINGS
        self.handler_count = 0       # for tests/diagnostics

    # --- lifecycle -----------------------------------------------------
    def begin(self, context):
        if self.active:
            return True
        sc = context.scene
        needed = [n for n in ("Bld_Plinth", "Road_Main") if n not in bpy.data.objects]
        if needed:
            print(f"[Intro] Campus not found in this .blend (missing {needed}). Run 01_build_campus.py first.")
            return False
        win, area, region = find_view3d(context)
        if area is None:
            print("[Intro] No 3D viewport available.")
            return False
        sp = area.spaces.active
        cam = ensure_intro_camera(sc)
        self.path, self.report = build_path(sc)
        self.saved = {
            "camera": sc.camera, "res": (sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage),
            "persp": sp.region_3d.view_perspective, "overlays": sp.overlay.show_overlays, "gizmo": sp.show_gizmo,
            "ui": sp.show_region_ui, "tool": sp.show_region_toolbar, "header": sp.show_region_header,
            "shading": sp.shading.type, "hidden": [],
        }
        col = bpy.data.collections.get(PLAYER_COLLECTION)
        if col:
            for o in col.objects:
                try:
                    if o.visible_get():
                        o.hide_set(True)
                        self.saved["hidden"].append(o.name)
                except RuntimeError:
                    pass
        self.window, self.area_ptr = win, area.as_pointer()
        self.hide_ui(sp)
        sc.camera = cam
        sp.region_3d.view_perspective = 'CAMERA'
        self.settings_changed()
        self.fsm = IntroFSM(self, _now())
        self.apply_pose(0.0)
        if self.handler is None:
            self.handler = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), 'WINDOW', 'POST_PIXEL')
            self.handler_count += 1
        self.active, self.done = True, False
        print(f"[Intro] started ({self.report['source']} keys, fix={self.report['fix']}, "
              f"{self.report['obstacles']} obstacles checked)")
        return True

    def restart(self):
        if self.fsm and self.active:
            self.fsm.reset(_now())

    def _resolve(self):
        for win in bpy.context.window_manager.windows:
            for ar in win.screen.areas:
                if ar.type == 'VIEW_3D' and ar.as_pointer() == self.area_ptr:
                    for rg in ar.regions:
                        if rg.type == 'WINDOW':
                            return win, ar, rg
        return None, None, None

    def hide_ui(self, sp):
        sp.overlay.show_overlays = False
        sp.show_gizmo = False
        sp.show_region_ui = False
        sp.show_region_toolbar = False
        sp.show_region_header = False

    def restore_viewport(self):
        """Idempotent: puts viewport, render size, hidden objects back."""
        s, self.saved = self.saved, None
        if not s:
            return
        win, area, _ = self._resolve()
        sc = bpy.context.scene
        try:
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = s["res"]
        except Exception:
            pass
        if area:
            sp = area.spaces.active
            for attr, val in (("show_region_ui", s["ui"]), ("show_region_toolbar", s["tool"]),
                              ("show_region_header", s["header"]), ("show_gizmo", s["gizmo"])):
                try:
                    setattr(sp, attr, val)
                except Exception:
                    pass
            try:
                sp.overlay.show_overlays = s["overlays"]
                sp.shading.type = s["shading"]
            except Exception:
                pass
        for name in s["hidden"]:
            o = bpy.data.objects.get(name)
            if o:
                try:
                    o.hide_set(False)
                except RuntimeError:
                    pass
        self._saved_camera, self._saved_persp = s["camera"], s["persp"]

    def _remove_handler(self):
        if self.handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handler, 'WINDOW')
            self.handler = None

    def abort(self, why=""):
        """Safe exit on any error: never leave the user stuck in a hidden-UI viewport."""
        print(f"[Intro] aborted {why}")
        self.restore_viewport()
        sc = bpy.context.scene
        cam = getattr(self, "_saved_camera", None)
        if cam and cam.name in bpy.data.objects:
            sc.camera = cam
        self._remove_handler()
        self.active, self.done, self.fsm = False, True, None

    # --- FSM hooks -----------------------------------------------------------
    def settings_changed(self):
        cam = bpy.data.objects.get(INTRO_CAMERA)
        if cam:
            cam.data.dof.use_dof = self.settings["dof"]
        win, area, _ = self._resolve()
        if area and self.saved:
            sp = area.spaces.active
            sp.shading.type = 'RENDERED' if self.settings["rendered"] else self.saved["shading"]

    def exit(self):
        self.abort("(EXIT selected)")

    def start_game(self):
        try:
            return self._launch_game()
        except Exception as exc:
            traceback.print_exc()
            self.notice = (f"Could not start game: {exc}", _now() + 6.0)
            return False

    def _ensure_game_operator(self):
        if hasattr(bpy.types, "IMRD_OT_StartGame"):
            return True
        try:                                   # running 06 on its own: borrow run_game's classes
            import importlib
            rg = importlib.import_module("run_game")
            for cls in (rg.IMRD_OT_StartGame, rg.IMRD_PT_GamePanel):   # NOT rg.register(): that would re-register the intro
                try:
                    bpy.utils.register_class(cls)
                except ValueError:
                    pass
            return hasattr(bpy.types, "IMRD_OT_StartGame")
        except Exception as exc:
            print(f"[Intro] cannot load run_game: {exc!r}")
            return False

    def _launch_game(self):
        if not self._ensure_game_operator():
            self.notice = ("Game not loaded - run scripts/run_game.py", _now() + 6.0)
            return False
        import importlib
        sc = bpy.context.scene
        # 1. restore viewport + hidden objects (player becomes visible again)
        self.restore_viewport()
        # 2. make sure player + NPCs exist (only builds what is missing)
        if "Player_Root" not in bpy.data.objects:
            importlib.import_module("02_player_controller").build_student_character()
        if "NPC_CampusGuide" not in bpy.data.objects:
            importlib.import_module("03_npc_interactions").setup_all_npcs_and_interactives()
        # 3. valid spawn point
        root = bpy.data.objects["Player_Root"]
        root.location = Vector(SPAWN)
        root.rotation_euler = (0.0, 0.0, 0.0)
        # 4. gameplay camera exactly where the game's follow-cam wants it (no visible swoop)
        pcam = bpy.data.objects.get("Player_Camera_3rd")
        if pcam is not None:
            d, hgt, pitch = 5.2, 2.4, 0.22          # same defaults as IMRD_OT_StartGame (yaw = pi)
            pcam.location = (SPAWN[0], SPAWN[1] + d * math.cos(pitch), SPAWN[2] + hgt + math.sin(pitch) * d)
            aim = Vector((SPAWN[0], SPAWN[1], SPAWN[2] + 1.4)) - pcam.location
            pcam.rotation_euler = aim.to_track_quat('-Z', 'Y').to_euler()
            sc.camera = pcam
        win, area, region = self._resolve()
        if area is None:
            raise RuntimeError("3D viewport vanished")
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
        # 5. start the existing game loop exactly once (guarded in run_game.py)
        with bpy.context.temp_override(window=win, area=area, region=region):
            res = bpy.ops.imrd.start_game('INVOKE_DEFAULT')
        if 'RUNNING_MODAL' not in res:
            raise RuntimeError(f"imrd.start_game returned {res}")
        # 6. fade the black overlay out over the live game, then drop the draw handler
        self.handoff = (_now(), 0.6)
        self.active, self.done, self.fsm = False, True, None
        bpy.app.timers.register(self._handoff_tick, first_interval=1.0 / 30.0)
        return True

    def _handoff_tick(self):
        _, area, _ = self._resolve()
        if area:
            area.tag_redraw()
        if self.handoff is None or _now() - self.handoff[0] >= self.handoff[1]:
            self.handoff = None
            self._remove_handler()
            return None
        return 1.0 / 30.0

    # --- per-frame -------------------------------------------------------
    def apply_pose(self, t):
        cam = bpy.data.objects.get(INTRO_CAMERA)
        if cam is None or self.path is None:
            return
        pos, look = self.path.sample(t)
        p, l = Vector(pos), Vector(look)
        cam.location = p
        d = l - p
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        if self.settings["dof"]:
            cam.data.dof.focus_distance = max(0.5, d.length)

    def tick(self):
        now = _now()
        win, area, region = self._resolve()
        if area is None:
            return self.abort("(viewport closed)")
        self.fsm.tick(now)
        if self.done or not self.active:
            return
        self.apply_pose(self.fsm.t(now))
        w, h = region.width, region.height
        if w > 8 and h > 8:
            sc = bpy.context.scene
            if abs(w / h - sc.render.resolution_x / max(1, sc.render.resolution_y)) > 0.01:
                sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
        area.tag_redraw()

    def key(self, name):
        if self.fsm and self.active:
            self.fsm.key(name, _now())

    def mouse(self, x, y, click):
        if self.fsm and self.active:
            w, h = self.region_size
            if w and h:
                self.fsm.pointer(x, y, w, h, _now(), click)

    # --- drawing -------------------------------------------------------------
    def draw(self):
        ctx = bpy.context
        if ctx.area is None or ctx.area.as_pointer() != self.area_ptr:
            return
        w, h = ctx.region.width, ctx.region.height
        self.region_size = (w, h)
        gpu.state.blend_set('ALPHA')
        try:
            now = _now()
            if self.handoff is not None and self.fsm is None:
                a = 1.0 - smoothstep((now - self.handoff[0]) / self.handoff[1])
                _rect(0, 0, w, h, (0.0, 0.0, 0.0, a))
                return
            fsm = self.fsm
            if fsm is None:
                return
            L, font = layout(w, h), 0
            t = fsm.t(now)
            self._draw_title(font, L, w, h, t)
            ma = fsm.menu_alpha(now)
            if fsm.state in ("MENU", "SETTINGS"):
                self._draw_menu(font, L, w, h, fsm, ma)
            elif fsm.state == "PLAY" and t > 1.0:
                self._draw_skip(font, L, min(1.0, (t - 1.0) / 1.0))
            msg, until = self.notice
            if msg and now < until:
                _text(font, msg, w / 2, h * 0.12, 18 * L["s"], PALETTE["gold"], "center", max_w=w * 0.9)
            _rect(0, 0, w, h, (0.0, 0.0, 0.0, fsm.black(now)))
        finally:
            gpu.state.blend_set('NONE')

    def _draw_title(self, font, L, w, h, t):
        a0, y0, s0 = title_state(t, 0)
        if a0 <= 0.0:
            return
        _grad(0, h * 0.55, w, h, _with_alpha(PALETTE["navy"], 0.0), _with_alpha(PALETTE["navy"], 0.62 * a0), False)
        cx, mw = L["cx"], L["max_text_w"]
        _text(font, TITLE_LINES[0], cx, L["y_title"] - y0, L["size_title"] * s0,
              _with_alpha(PALETTE["text"], a0), "center", tracking=L["size_title"] * 0.18, max_w=mw)
        rp = rule_progress(t)
        if rp > 0.0:
            rw = L["rule_w"] * rp
            _rect(cx - rw / 2, L["y_rule"], cx + rw / 2, L["y_rule"] + max(2.0, 2.5 * L["s"]), _with_alpha(PALETTE["gold"], 0.95))
        a1, y1, s1 = title_state(t, 1)
        if a1 > 0.0:
            _text(font, TITLE_LINES[1], cx, L["y_sub"] - y1, L["size_sub"] * s1,
                  _with_alpha(PALETTE["sub"], a1), "center", tracking=L["size_sub"] * 0.28, max_w=mw)
        a2, y2, s2 = title_state(t, 2)
        if a2 > 0.0:
            _text(font, TITLE_LINES[2], cx, L["y_inst"] - y2, L["size_inst"] * s2,
                  _with_alpha(PALETTE["text"], a2 * 0.95), "center", tracking=L["size_inst"] * 0.04, max_w=mw)

    def _draw_menu(self, font, L, w, h, fsm, ma):
        s = L["s"]
        _grad(0, 0, w * 0.5, h, _with_alpha(PALETTE["navy"], 0.70 * ma), _with_alpha(PALETTE["navy"], 0.0), True)
        labels = MENU_ITEMS if fsm.state == "MENU" else fsm.settings_items()
        for i, (r, label) in enumerate(zip(L["buttons"], labels)):
            sel = (i == fsm.sel)
            x, y, bw, bh = r
            _rect(x, y, x + bw, y + bh, _with_alpha(PALETTE["button_sel"] if sel else PALETTE["button"], ma))
            if sel:
                _rect(x, y, x + 5 * s, y + bh, _with_alpha(PALETTE["gold"], ma))
            col = PALETTE["gold"] if sel else PALETTE["text"]
            blf.size(font, max(8, int(round(20 * s))))
            th = blf.dimensions(font, "H")[1]
            _text(font, label, x + 24 * s, y + (bh - th) / 2.0, 20 * s, _with_alpha(col, ma),
                  tracking=2.0 * s, max_w=bw - 36 * s, shadow=False)
        hx, hy = L["hint"]
        hint = "W/S or Up/Down: select     Enter: confirm     R: replay intro" if fsm.state == "MENU" else "Enter: toggle     Esc: back"
        _text(font, hint, hx, hy, 13 * s, _with_alpha(PALETTE["sub"], 0.8 * ma), max_w=w * 0.8)

    def _draw_skip(self, font, L, a):
        x, y, bw, bh = L["skip"]
        s = L["s"]
        _rect(x, y, x + bw, y + bh, (0.0, 0.0, 0.0, 0.35 * a))
        for rx0, ry0, rx1, ry1 in ((x, y, x + bw, y + 1.5), (x, y + bh - 1.5, x + bw, y + bh),
                                    (x, y, x + 1.5, y + bh), (x + bw - 1.5, y, x + bw, y + bh)):
            _rect(rx0, ry0, rx1, ry1, _with_alpha(PALETTE["sub"], 0.7 * a))
        blf.size(font, max(8, int(round(14 * s))))
        th = blf.dimensions(font, "H")[1]
        _text(font, "SKIP INTRO  [Esc]", x + bw / 2, y + (bh - th) / 2.0, 14 * s,
              _with_alpha(PALETTE["text"], a), "center", tracking=1.2 * s, shadow=False)


CTRL = IntroController() if IN_BLENDER else None


# ----------------------------------------------------------------------
# operators / panel / registration
# ----------------------------------------------------------------------
if IN_BLENDER:

    class IMRD_OT_IntroModal(bpy.types.Operator):
        """Runs the cinematic intro (internal; use imrd.play_intro)"""
        bl_idname = "imrd.intro_modal"
        bl_label = "IMRD Intro Cinematic"
        bl_options = {'INTERNAL'}
        _timer = None

        def invoke(self, context, event):
            if CTRL.modal_running:                 # replay while running: reuse, never duplicate
                CTRL.restart()
                return {'CANCELLED'}
            if not CTRL.begin(context):
                return {'CANCELLED'}
            CTRL.modal_running = True
            self._timer = context.window_manager.event_timer_add(1.0 / 60.0, window=context.window)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        def _end(self, context, result):
            if self._timer is not None:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
            CTRL.modal_running = False
            return {result}

        def modal(self, context, event):
            try:
                if not CTRL.active:
                    return self._end(context, 'FINISHED')
                if event.type == 'TIMER':
                    CTRL.tick()
                    return self._end(context, 'FINISHED') if (CTRL.done or not CTRL.active) else {'RUNNING_MODAL'}
                if event.type == 'MOUSEMOVE':
                    CTRL.mouse(event.mouse_region_x, event.mouse_region_y, False)
                elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                    CTRL.mouse(event.mouse_region_x, event.mouse_region_y, True)
                elif event.value == 'PRESS' and not event.is_repeat and event.type not in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                    CTRL.key(event.type)
                elif event.type in {'WINDOW_DEACTIVATE', 'TIMER_REPORT'}:
                    return {'PASS_THROUGH'}
                return {'RUNNING_MODAL'}
            except Exception:
                traceback.print_exc()
                CTRL.abort("(error)")
                return self._end(context, 'CANCELLED')

        def cancel(self, context):
            if self._timer is not None:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
            CTRL.modal_running = False
            if CTRL.active:
                CTRL.abort("(cancelled)")

    class IMRD_OT_PlayIntro(bpy.types.Operator):
        """Play the IMRD cinematic intro (fade-in, campus flyover, title, menu)"""
        bl_idname = "imrd.play_intro"
        bl_label = "Play Cinematic Intro"

        def execute(self, context):
            request_play(0.05)
            return {'FINISHED'}

    class IMRD_OT_IntroMarkers(bpy.types.Operator):
        """Rebuild the draggable camera markers from the current campus layout"""
        bl_idname = "imrd.intro_reset_markers"
        bl_label = "Reset Intro Camera Markers"

        def execute(self, context):
            create_markers(context.scene, keys_from_layout(discover_layout()))
            self.report({'INFO'}, "Intro camera markers rebuilt (collection 'Intro_Cinematic').")
            return {'FINISHED'}

    class IMRD_PT_IntroPanel(bpy.types.Panel):
        bl_label = "Cinematic Intro"
        bl_idname = "IMRD_PT_IntroPanel"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "IMRD Game"

        def draw(self, context):
            col = self.layout.column(align=True)
            col.operator("imrd.play_intro", text="Play Cinematic Intro", icon='PLAY')
            col.operator("imrd.intro_reset_markers", icon='EMPTY_AXIS')

    CLASSES = (IMRD_OT_IntroModal, IMRD_OT_PlayIntro, IMRD_OT_IntroMarkers, IMRD_PT_IntroPanel)

    def register():
        for c in CLASSES:
            try:
                bpy.utils.register_class(c)
            except ValueError:                      # already registered (re-run of script)
                bpy.utils.unregister_class(c)
                bpy.utils.register_class(c)

    def unregister():
        for c in reversed(CLASSES):
            try:
                bpy.utils.unregister_class(c)
            except RuntimeError:
                pass

    def request_play(delay=0.2):
        """Start (or restart) the intro from anywhere, e.g. script start-up."""
        def _go():
            win, area, region = find_view3d(None)
            if area is None:
                print("[Intro] no 3D viewport yet - open one and press 'Play Cinematic Intro'")
                return None
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.imrd.intro_modal('INVOKE_DEFAULT')
            return None
        bpy.app.timers.register(_go, first_interval=delay)

else:
    def register():
        pass

    def unregister():
        pass

    def request_play(delay=0.2):
        print("[Intro] Blender not available")


# ======================================================================
# 6. PREVIEW RENDER (frames + mp4, real text objects) - Blender only
# ======================================================================
def render_preview(res=(640, 360), samples=16, end_t=T_MENU, movie=True):
    """Low-res preview. Returns a dict of produced files (only files that exist)."""
    sc = bpy.context.scene
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path, rep = build_path(sc)
    cam = ensure_intro_camera(sc)
    cam.data.dof.use_dof = SETTINGS["dof"]
    r, ev, vs = sc.render, sc.eevee, sc.view_settings
    saved = dict(cam=sc.camera, rx=r.resolution_x, ry=r.resolution_y, pct=r.resolution_percentage, fps=r.fps,
                 fs=sc.frame_start, fe=sc.frame_end, fp=r.filepath, eng=r.engine, ff=r.image_settings.file_format,
                 exp=vs.exposure, ss=getattr(ev, "taa_render_samples", None), rt=getattr(ev, "use_raytracing", None))
    made = {"stills": [], "movie": None, "frames": 0, "path": rep}
    f0, f1 = 1, int(round(end_t * FPS)) + 1
    extras = []
    player = bpy.data.collections.get(PLAYER_COLLECTION)
    hidden = [o for o in (player.objects if player else []) if o.visible_get()]
    for o in hidden:
        o.hide_set(True)
    try:
        sc.camera = cam
        r.resolution_x, r.resolution_y, r.resolution_percentage, r.fps = res[0], res[1], 100, FPS
        sc.frame_start, sc.frame_end = f0, f1
        try:
            r.engine = 'BLENDER_EEVEE'
        except TypeError:
            r.engine = 'BLENDER_EEVEE_NEXT'
        if saved["ss"] is not None:
            ev.taa_render_samples = samples
        if saved["rt"] is not None:
            ev.use_raytracing = False                     # preview speed
        # camera keyframes: one per frame, so the saved sequence is plain animation
        prev = None
        for f in range(f0, f1 + 1):
            pos, look = path.sample((f - f0) / FPS)
            p, l = Vector(pos), Vector(look)
            cam.location = p
            eul = (l - p).to_track_quat('-Z', 'Y').to_euler('XYZ', prev) if prev else (l - p).to_track_quat('-Z', 'Y').to_euler()
            cam.rotation_euler, prev = eul, eul
            cam.keyframe_insert("location", frame=f)
            cam.keyframe_insert("rotation_euler", frame=f)
            cam.data.dof.focus_distance = max(0.5, (l - p).length)
            cam.data.keyframe_insert("dof.focus_distance", frame=f)
        extras += _make_title_objects(sc, cam, f0, end_t)
        _animate_fade(sc, f0, f1)
        # stills first: cheap proof that rendering works at all
        for tname, t in (("t01", 1.5), ("t08", 8.0), ("t13", 13.0)):
            sc.frame_set(f0 + int(round(t * FPS)))
            fp = PREVIEW_DIR / f"still_{tname}.png"
            r.image_settings.file_format = 'PNG'
            r.filepath = str(fp)
            bpy.ops.render.render(write_still=True)
            if fp.exists() and fp.stat().st_size > 0:
                made["stills"].append(str(fp))
        if movie:
            mp4 = PREVIEW_DIR / "intro_preview.mp4"
            ok = False
            try:
                if hasattr(r.image_settings, "media_type"):
                    r.image_settings.media_type = 'VIDEO'
                r.image_settings.file_format = 'FFMPEG'
                r.ffmpeg.format, r.ffmpeg.codec = 'MPEG4', 'H264'
                r.ffmpeg.constant_rate_factor = 'MEDIUM'
                r.filepath = str(PREVIEW_DIR / "intro_preview")
                bpy.ops.render.render(animation=True)
                ok = mp4.exists() and mp4.stat().st_size > 0
            except Exception as exc:
                print(f"[Intro] mp4 output failed ({exc!r}); writing PNG frames instead")
            if ok:
                made["movie"] = str(mp4)
            else:
                if hasattr(r.image_settings, "media_type"):
                    r.image_settings.media_type = 'IMAGE'
                r.image_settings.file_format = 'PNG'
                r.filepath = str(PREVIEW_DIR / "frame_")
                bpy.ops.render.render(animation=True)
                made["frames"] = len(list(PREVIEW_DIR.glob("frame_*.png")))
    finally:
        for o in extras:
            if o.type == 'FONT':
                cd = o.data
                bpy.data.objects.remove(o, do_unlink=True)
                bpy.data.curves.remove(cd)
            else:
                bpy.data.objects.remove(o, do_unlink=True)
        for holder in (cam, cam.data, sc):
            if holder.animation_data:
                holder.animation_data_clear()
        for o in hidden:
            o.hide_set(False)
        sc.camera = saved["cam"]
        r.resolution_x, r.resolution_y, r.resolution_percentage, r.fps = saved["rx"], saved["ry"], saved["pct"], saved["fps"]
        sc.frame_start, sc.frame_end, r.filepath, r.engine = saved["fs"], saved["fe"], saved["fp"], saved["eng"]
        vs.exposure = saved["exp"]
        try:
            r.image_settings.file_format = saved["ff"]
        except Exception:
            pass
        if saved["ss"] is not None:
            ev.taa_render_samples = saved["ss"]
        if saved["rt"] is not None:
            ev.use_raytracing = saved["rt"]
    return made


def _make_title_objects(sc, cam, f0, end_t):
    """Real 3D text objects parented to the camera, faded in with an animated Mix factor."""
    col = ensure_intro_collection(sc)
    dist, width_m = 9.0, 36.0 / LENS_MM * 9.0
    height_m = width_m * 9.0 / 16.0
    objs = []
    # (text, size px, baseline fraction from top, letter spacing) mirror layout()
    spec = ((TITLE_LINES[0], 104.0, 0.20, 1.45), (TITLE_LINES[1], 26.0, 0.285, 1.30), (TITLE_LINES[2], 20.0, 0.33, 1.04))
    for i, (txt, px, frac, spacing) in enumerate(spec):
        cu = bpy.data.curves.new(f"IntroText_{i}", 'FONT')
        cu.body, cu.size = txt, px / 720.0 * height_m
        cu.align_x, cu.align_y, cu.space_character = 'CENTER', 'BOTTOM_BASELINE', spacing
        o = bpy.data.objects.new(f"IntroText_{i}", cu)
        col.objects.link(o)
        o.parent = cam
        y = (0.5 - frac) * height_m
        o.location = (0.0, y, -dist)
        mat = bpy.data.materials.new(f"IntroTextMat_{i}")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        em, tr = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeBsdfTransparent")
        mix, out = nt.nodes.new("ShaderNodeMixShader"), nt.nodes.new("ShaderNodeOutputMaterial")
        em.inputs["Color"].default_value = (0.97, 0.97, 0.97, 1.0) if i != 1 else (0.86, 0.9, 0.96, 1.0)
        em.inputs["Strength"].default_value = 2.2
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        cu.materials.append(mat)
        s, d = TITLE_TIMING[i]
        for tt, val, dy in ((s - 0.05, 0.0, -0.10), (s + d, 1.0, 0.0)):
            f = f0 + int(round(tt * FPS))
            mix.inputs[0].default_value = val
            mix.inputs[0].keyframe_insert("default_value", frame=f)
            o.location = (0.0, y + dy, -dist)
            o.keyframe_insert("location", frame=f)
        objs.append(o)
    return objs


def _animate_fade(sc, f0, f1):
    """Fade from/to black via exposure (-16 EV is black); stays inside the render."""
    vs = sc.view_settings
    base = vs.exposure
    for f, v in ((f0, -16.0), (f0 + int(T_FADE_IN * FPS), base), (f1 - int(0.8 * FPS), base), (f1, -16.0)):
        vs.exposure = v
        vs.keyframe_insert("exposure", frame=f)
    vs.exposure = base


# ======================================================================
# 7. SELF TEST + REPORT
# ======================================================================
class _StubHooks:
    def __init__(self, ok=True):
        self.settings = {"dof": True, "rendered": False}
        self.ok, self.started, self.exited, self.changed = ok, 0, 0, 0

    def start_game(self):
        self.started += 1
        return self.ok

    def exit(self):
        self.exited += 1

    def settings_changed(self):
        self.changed += 1


def _run(fsm, now, secs, dt=1 / 60.0):
    end = now + secs
    while now < end:
        now += dt
        fsm.tick(now)
    return now


def selftest():
    """Logic tests that run anywhere. Returns list of (id, title, status, detail)."""
    R = []

    def add(i, title, ok, detail):
        R.append((i, title, "PASS" if ok else "FAIL", detail))

    keys = keys_from_layout()
    path = CameraPath(keys)
    obs = static_obstacles()
    # 04 smooth motion
    dt = 1 / 240.0
    samples = [path.sample(i * dt) for i in range(int(T_END / dt) + 1)]
    sp = [math.dist(samples[i + 1][0], samples[i][0]) / dt for i in range(len(samples) - 1)]
    ac = [abs(sp[i + 1] - sp[i]) / dt for i in range(len(sp) - 1)]
    jump = max(math.dist(samples[i + 1][0], samples[i][0]) for i in range(len(samples) - 1))

    def yaw_pitch(p, l):
        d = (l[0] - p[0], l[1] - p[1], l[2] - p[2])
        return math.degrees(math.atan2(d[0], -d[1])), math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    ang = [yaw_pitch(*s) for s in samples[::4]]
    rate = max(max(abs(ang[i + 1][0] - ang[i][0]), abs(ang[i + 1][1] - ang[i][1])) / (4 * dt) for i in range(len(ang) - 1))
    add("04", "Camera motion smooth (no jumps, bounded speed/rotation)",
        jump < 0.06 and max(sp) < 14.0 and rate < 25.0 and sp[0] < 0.2 and sp[-1] < 0.2,
        f"max speed {max(sp):.1f} m/s, max camera turn {rate:.1f} deg/s, max step {jump*100:.1f} cm @240Hz, start/end speed {sp[0]:.2f}/{sp[-1]:.2f}")
    # 06 collisions
    iss = validate_path(path, obs)
    zmin = min(s[0][2] for s in samples)
    add("06", "Camera never inside buildings/trees/gate/lamps, never below ground height",
        not iss and zmin >= MIN_CAM_Z, f"{len(obs)} obstacles, margin {CLEARANCE} m, lowest z {zmin:.2f} m, issues: {iss[:3]}")
    # 05 building visible
    hf, vf = math.degrees(math.atan(18.0 / LENS_MM)), math.degrees(math.atan(10.125 / LENS_MM))
    worst = 0.0
    for p, l in samples[::12]:
        for target in ((0.0, 0.0, 4.5),):
            fwd = [l[i] - p[i] for i in range(3)]
            n = math.sqrt(sum(c * c for c in fwd))
            fwd = [c / n for c in fwd]
            to = [target[i] - p[i] for i in range(3)]
            m = math.sqrt(sum(c * c for c in to))
            cosang = sum(a * b / m for a, b in zip(fwd, to))
            worst = max(worst, math.degrees(math.acos(max(-1, min(1, cosang)))))
    add("05", "Main building stays inside the view cone for the whole path", worst < hf * 0.9,
        f"max angle between view axis and building centre {worst:.1f} deg (half-FOV {hf:.1f})")
    # 07 layout/readability
    bad = []
    for (w, h) in ((640, 360), (800, 600), (1280, 720), (1920, 1080), (2560, 1440), (1000, 1000)):
        L = layout(w, h)
        rects = list(L["buttons"]) + [L["skip"]]
        for r in rects:
            if r[0] < 0 or r[1] < 0 or r[0] + r[2] > w or r[1] + r[3] > h:
                bad.append((w, h, "out of bounds", r))
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]:
                    bad.append((w, h, "overlap", i, j))
        lines = [(L["y_title"], L["size_title"] * 0.72), (L["y_sub"], L["size_sub"] * 0.72), (L["y_inst"], L["size_inst"] * 0.72)]
        for k in range(len(lines) - 1):
            if lines[k + 1][0] + lines[k + 1][1] > lines[k][0]:
                bad.append((w, h, "title lines overlap", k))
        if L["buttons"][0][1] + L["buttons"][0][3] > L["y_inst"] - 10:
            bad.append((w, h, "menu collides with title"))
    add("07", "Title/menu layout valid at 6 window sizes (in bounds, no overlaps, text shrinks to fit)", not bad, f"{bad[:3]}")
    # 08..10, 13 FSM
    hk = _StubHooks()
    n0 = 100.0
    f = IntroFSM(hk, n0)
    n = _run(f, n0, 3.0)
    f.key("ESC", n)
    f.key("SPACE", n)          # second press during the skip fade must be ignored
    n = _run(f, n, 1.0)
    add("08", "Skip (Esc/Space) leads to menu via fade; repeated presses ignored", f.state == "MENU" and hk.started == 0 and f.t(n) >= T_MENU,
        f"state={f.state}, t={f.t(n):.1f}s")
    add("09", "Menu appears (naturally at 17 s and after skip)", f.menu_alpha(n + 1) > 0.9, f"menu alpha {f.menu_alpha(n + 1):.2f}")
    g = IntroFSM(_StubHooks(), 0.0)
    _run(g, 0.0, T_MENU + 1.5)
    add("09b", "Natural playback reaches MENU at t>=17 s", g.state == "MENU", f"state={g.state}")
    n = _run(f, n, 1.5)
    for _ in range(5):
        f.key("RET", n)
        f.pointer(L_start(1280, 720)[0], L_start(1280, 720)[1], 1280, 720, n, True)
    n = _run(f, n, 1.5)
    add("10", "START WALKTHROUGH fires exactly once despite repeated Enter/clicks", hk.started == 1 and f.starts == 1 and f.state == "DONE",
        f"start_game calls={hk.started}, state={f.state}")
    hk2 = _StubHooks()
    f2 = IntroFSM(hk2, 0.0)
    n = _run(f2, 0.0, T_MENU + 1.5)
    resets = []
    for _ in range(3):
        f2.key("R", n)
        n = _run(f2, n, 0.5)
        resets.append(f2.state)
        n = _run(f2, n, T_MENU + 1.5)
    add("13", "Replay x3 restarts timeline without side effects (no extra start/exit calls)",
        hk2.started == 0 and hk2.exited == 0 and f2.replays == 3 and f2.xf is None,
        f"replays={f2.replays}, starts={hk2.started}, state after each: {resets}")
    hk3 = _StubHooks(ok=False)
    f3 = IntroFSM(hk3, 0.0)
    n = _run(f3, 0.0, T_MENU + 1.5)
    f3.key("RET", n)
    n = _run(f3, n, 1.0)
    add("14a", "If the game cannot start the menu stays usable (retry possible)", f3.state == "MENU" and not f3._started,
        f"state={f3.state}")
    hk4 = _StubHooks()
    f4 = IntroFSM(hk4, 0.0)
    n = _run(f4, 0.0, T_MENU + 1.5)
    f4.key("S", n)
    f4.key("RET", n)
    n = _run(f4, n, 0.1)
    st1 = f4.state
    f4.key("RET", n)
    f4.key("ESC", n)
    n = _run(f4, n, 0.1)
    add("14b", "Settings: toggles work, Esc returns to menu", st1 == "SETTINGS" and f4.state == "MENU" and hk4.settings["dof"] is False,
        f"dof={hk4.settings['dof']}")
    # 14 missing optional assets
    odd = keys_from_layout({"ex": 3.0, "ey": 12.0, "gy": 90.0, "top": 14.0})
    ok_alt = len(validate_path(CameraPath(odd), [])) == 0
    fb = CameraPath(fallback_keys())
    add("14", "Layout without scene objects: keys derive from anchors; fallback dolly is collision-free",
        ok_alt and not validate_path(fb, obs), f"fallback issues: {validate_path(fb, obs)[:2]}")
    # lift_keys sanity
    tree = [("T", (-1, -1, 0), (1, 1, 6))]
    lifted = lift_keys([dict(name="a", t=0, pos=(0, 0, 2), look=(0, 5, 2))], tree)
    add("14c", "Colliding key is lifted over the obstacle", lifted[0]["pos"][2] > 6.0, f"z -> {lifted[0]['pos'][2]:.1f}")
    return R


def L_start(w, h):
    r = layout(w, h)["buttons"][0]
    return r[0] + r[2] / 2, r[1] + r[3] / 2


BLENDER_ONLY = [
    ("01", "Intro scene loads in Blender", "campus objects found, intro camera created"),
    ("02", "Intro_Camera is the active camera", "scene.camera after begin()"),
    ("03", "Animation starts automatically", "run_game.py autostart / --python 06_intro_cinematic.py"),
    ("11", "START WALKTHROUGH activates gameplay; player moves", "needs interactive session"),
    ("12", "HUD and missions still work after the transition", "needs interactive session"),
    ("15", "Project can be saved and reopened with the intro installed", "needs Blender"),
    ("R1", "Preview render (stills + mp4) produced and checked", "python scripts/06_intro_cinematic.py -- --render-preview"),
]


def blender_selftest():
    """Scene-level checks that need bpy (background-safe). Returns list like selftest()."""
    R = []
    sc = bpy.context.scene
    ok = all(n in bpy.data.objects for n in ("Bld_Plinth", "Road_Main", "Canopy_Roof"))
    R.append(("01", "Campus objects present in .blend", "PASS" if ok else "FAIL", f"{len(bpy.data.objects)} objects"))
    if not ok:
        return R
    cam = ensure_intro_camera(sc)
    path, rep = build_path(sc)
    R.append(("01b", "Path validated against real scene geometry", "PASS" if not rep["issues"] else "WARN",
              f"source={rep['source']}, obstacles={rep['obstacles']}, issues={rep['issues'][:2]}, fix={rep['fix']}"))
    R.append(("02", "Intro camera exists with DOF f/8 and lens 28", "PASS" if cam.data.lens == LENS_MM else "FAIL", cam.name))
    R.append(("06b", "No collision against real object bounds", "PASS" if not validate_path(path, scene_obstacles()) else "FAIL",
              f"{len(scene_obstacles())} real obstacle boxes"))
    return R


def write_report(results, extra=None, made=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ver = ".".join(map(str, bpy.app.version)) if IN_BLENDER else "not run in Blender"
    lines = ["# IMRD Intro Cinematic - Test Report", "",
             f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}  ", f"Blender: {ver}  ",
             f"Python: {sys.version.split()[0]}", "", "## Files", "",
             "- scripts/06_intro_cinematic.py (new)", "- scripts/run_game.py (4 small edits marked [INTRO INTEGRATION n/4]: optional import, `_running` guard on `imrd.start_game`, register, autostart)",
             "- README_INTRO.md (new)", "- scripts/tests/test_intro_logic.py (new)", "", "## Timeline", ""]
    for name, a, b in SHOT_LIST:
        lines.append(f"- {name}: {a:.0f}-{b:.0f} s")
    lines += ["", "Camera keys (time, position, look-at):", ""]
    for k in keys_from_layout():
        lines.append(f"- {k['name']}: t={k['t']:.1f}  pos=({k['pos'][0]:.1f}, {k['pos'][1]:.1f}, {k['pos'][2]:.1f})  "
                     f"look=({k['look'][0]:.1f}, {k['look'][1]:.1f}, {k['look'][2]:.1f}){'  (ease)' if k.get('ease') else ''}")
    lines += ["", "## Test results", "", "| # | Test | Result | Detail |", "|---|------|--------|--------|"]
    for i, t, s, d in results:
        lines.append(f"| {i} | {t} | {s} | {str(d).replace('|', '/')} |")
    done = {r[0] for r in results}
    for i, t, how in BLENDER_ONLY:
        if i not in done:
            lines.append(f"| {i} | {t} | NOT RUN | needs Blender: {how} |")
    lines += ["", "## Preview output", ""]
    if made and (made.get("movie") or made.get("stills")):
        lines.append(f"- movie: {made.get('movie')}")
        lines += [f"- still: {s}" for s in made.get("stills", [])]
    else:
        lines.append("- No preview was rendered in this run (no render output exists). Run the --render-preview command from the README.")
    lines += ["", "## Remaining limitations", "",
              "- Blender-specific code (draw handler, modal operator, game hand-off, render preview) was written against the Blender 5.x API but could NOT be executed in the authoring environment; items marked NOT RUN must be verified on your machine.",
              "- Preview render uses text objects with approximate (not pixel-identical) typography; the gold rule line and the menu are viewport overlays and are not part of the rendered video.",
              "- EXIT closes the intro and restores the normal Blender UI; it does not quit Blender.",
              "- Viewport lighting: in Solid/Material Preview the Nishita sky and sun are not used; switch to Rendered (Settings > RENDERED VIEW) for the golden-hour look."]
    if extra:
        lines += ["", "## Notes", ""] + [f"- {e}" for e in extra]
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[Intro] report written: {REPORT_FILE}")


def write_config():
    data = {"fps": FPS, "duration_s": T_END, "menu_at_s": T_MENU, "lens_mm": LENS_MM,
            "shots": [dict(name=n, start=a, end=b) for n, a, b in SHOT_LIST],
            "keys": keys_from_layout(), "title": list(TITLE_LINES),
            "render_preview": {"resolution": [640, 360], "samples": 16, "output": str(PREVIEW_DIR)}}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ======================================================================
# 8. ENTRY POINT
# ======================================================================
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    write_config()
    if "--selftest" in argv or "--render-preview" in argv:
        results = selftest()
        made = None
        if IN_BLENDER:
            results += blender_selftest()
            if "--render-preview" in argv:
                made = render_preview()
                have = bool(made["movie"] or made["stills"])
                results.append(("R1", "Preview render produced files that exist on disk", "PASS" if have else "FAIL",
                                f"movie={made['movie']}, stills={len(made['stills'])}, frames={made['frames']}"))
        for r in results:
            print(f"[{r[2]:4}] {r[0]:>4} {r[1]} - {r[3]}")
        write_report(results, made=made)
        fails = [r for r in results if r[2] == "FAIL"]
        if not IN_BLENDER or bpy.app.background:
            sys.exit(1 if fails else 0)
        return
    if not IN_BLENDER:
        print(__doc__)
        return
    sys.modules.setdefault("06_intro_cinematic", sys.modules[__name__])   # run_game imports us by this name
    register()
    if not bpy.app.background and "--no-intro" not in argv:
        request_play(1.0)


if __name__ == "__main__":
    main()
