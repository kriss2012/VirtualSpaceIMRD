"""
Interactive flat-panel display (65") on a rolling stand, showing a procedural
blue "Windows-style" desktop. Includes wall, door and potted plant.
Blender 3.0+ / 4.x

HOW TO RUN: Scripting workspace -> Text > Open -> this file -> Alt+P.
            Numpad 0 = camera view, F12 = render.

Panel faces -Y, up is Z, everything is parented to "Panel_Root".
"""
import math
import random
from math import exp, pi, radians

import bpy
from mathutils import Vector

random.seed(4)
USE_CYCLES = True

SCREEN_W = 1.40
SCREEN_H = SCREEN_W * 9 / 16
BOTTOM_Z = 0.92              # underside of the panel above the floor

# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene
root = bpy.data.objects.new("Panel_Root", None)
scene.collection.objects.link(root)


def set_in(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return


def make_mat(name, color, metallic=0.0, rough=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    set_in(b, ["Base Color"], (*color, 1))
    set_in(b, ["Metallic"], metallic)
    set_in(b, ["Roughness"], rough)
    return m


def adopt(o, mat=None, smooth=False):
    if mat:
        o.data.materials.append(mat)
    if smooth:
        bpy.context.view_layer.objects.active = o
        for p in o.data.polygons:
            p.use_smooth = True
    o.parent = root
    return o


def box(name, center, size, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    return adopt(o, mat)


def beam(name, p1, p2, r, mat, segs=16):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(vertices=segs, radius=r, depth=d.length, location=(p1 + p2) / 2)
    o = bpy.context.active_object
    o.name = name
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return adopt(o, mat, smooth=True)


# ----------------------------------------------------------------------------
# Procedural desktop picture (blue gradient, light beam, 4-pane logo, icons, taskbar)
# ----------------------------------------------------------------------------
def make_desktop_image(w=480, h=270):
    img = bpy.data.images.new("Desktop_Wallpaper", w, h)
    px = [0.0] * (w * h * 4)
    icon_cols = [(0.9, 0.9, 0.9), (0.2, 0.7, 0.3), (0.9, 0.55, 0.1), (0.3, 0.6, 0.95),
                 (0.8, 0.8, 0.85), (0.2, 0.8, 0.5), (0.95, 0.4, 0.2), (0.9, 0.9, 0.3)]
    for j in range(h):
        y = j / (h - 1)
        for i in range(w):
            x = i / (w - 1)
            t = 0.75 * x + 0.25 * y
            r, g, b = 0.01 + 0.05 * t, 0.06 + 0.30 * t, 0.28 + 0.62 * t
            # diagonal light beam through the logo
            beam_d = (y - 0.56) - 0.22 * (x - 0.78)
            glow = exp(-(beam_d ** 2) / 0.012) * 0.30 * min(1.0, max(0.0, (x - 0.15) * 1.6))
            r, g, b = r + glow * 0.5, g + glow * 0.8, b + glow
            # window logo (four panes)
            for (x0, x1) in ((0.675, 0.755), (0.775, 0.855)):
                for (y0, y1) in ((0.50, 0.62), (0.64, 0.78)):
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        r, g, b = 0.45, 0.78, 1.0
            # desktop icons on the left
            for k, ic in enumerate(icon_cols):
                cy = 0.90 - k * 0.105
                if 0.016 <= x <= 0.050 and cy - 0.028 <= y <= cy + 0.028:
                    r, g, b = ic
            # taskbar
            if y < 0.05:
                r, g, b = 0.015, 0.02, 0.05
                if 0.015 <= x <= 0.04:
                    r, g, b = 0.2, 0.5, 0.9
            idx = (j * w + i) * 4
            px[idx:idx + 4] = (min(r, 1.0), min(g, 1.0), min(b, 1.0), 1.0)
    img.pixels = px
    img.pack()
    return img


screen_img = make_desktop_image()

screen_m = bpy.data.materials.new("Screen")
screen_m.use_nodes = True
snt = screen_m.node_tree
sb = snt.nodes["Principled BSDF"]
set_in(sb, ["Base Color"], (0, 0, 0, 1))
set_in(sb, ["Roughness"], 0.08)
tex = snt.nodes.new("ShaderNodeTexImage")
tex.image = screen_img
for name in ("Emission Color", "Emission"):
    if name in sb.inputs:
        snt.links.new(tex.outputs["Color"], sb.inputs[name])
        break
set_in(sb, ["Emission Strength"], 1.0)

silver = make_mat("Aluminium", (0.75, 0.76, 0.78), metallic=1.0, rough=0.3)
black = make_mat("Black_Metal", (0.012, 0.012, 0.015), metallic=0.4, rough=0.45)
glass = make_mat("Glass_Black", (0.003, 0.003, 0.005), rough=0.05)
rubber = make_mat("Rubber", (0.02, 0.02, 0.02), rough=0.8)

# ----------------------------------------------------------------------------
# Panel
# ----------------------------------------------------------------------------
OUT_W = SCREEN_W + 0.07
OUT_H = SCREEN_H + 0.105
ZC = BOTTOM_Z + OUT_H / 2           # panel centre height
Y_PANEL = -0.06
SCR_Z = BOTTOM_Z + 0.07 + SCREEN_H / 2

box("Panel_Body", (0, Y_PANEL, ZC), (OUT_W, 0.07, OUT_H), silver)
box("Panel_Glass", (0, Y_PANEL - 0.037, SCR_Z), (SCREEN_W + 0.03, 0.006, SCREEN_H + 0.03), glass)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, Y_PANEL - 0.0405, SCR_Z), rotation=(pi / 2, 0, 0))
scr = bpy.context.active_object
scr.name = "Screen"
scr.scale = (SCREEN_W, SCREEN_H, 1)
adopt(scr, screen_m)

# lower bezel details: speaker grilles, buttons
for sx in (-1, 1):
    box("Grille", (sx * 0.30, Y_PANEL - 0.036, BOTTOM_Z + 0.032), (0.24, 0.004, 0.014), black)
for k in range(5):
    box("Button", (-0.62 + k * 0.045, Y_PANEL - 0.036, BOTTOM_Z + 0.032), (0.02, 0.004, 0.008), black)

# ----------------------------------------------------------------------------
# Rolling stand
# ----------------------------------------------------------------------------
BASE_Z = 0.10
box("Base", (0, 0.0, BASE_Z), (1.32, 0.62, 0.045), black)
for sx in (-1, 1):
    x = sx * 0.50
    box(f"Post_{sx}", (x, 0.01, BASE_Z + 0.65), (0.05, 0.045, 1.30), black)
    beam(f"Leg_Brace_{sx}", (x, 0.01, 0.60), (sx * 0.60, 0.01, BASE_Z + 0.02), 0.026, black)
    beam(f"Leg_Brace_In_{sx}", (x, 0.01, 0.60), (sx * 0.40, 0.01, BASE_Z + 0.02), 0.020, black)
    box(f"Bracket_{sx}", (x, -0.015, BOTTOM_Z + 0.30), (0.06, 0.05, 0.14), black)

box("Shelf", (0, 0.0, 0.62), (0.96, 0.32, 0.03), black)
beam("Pen", (-0.05, -0.04, 0.645), (0.12, -0.02, 0.645), 0.007, make_mat("Pen", (0.1, 0.2, 0.7)), 10)

# casters
for sx in (-1, 1):
    for sy in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.035, depth=0.03,
                                            location=(sx * 0.62, sy * 0.26, 0.04), rotation=(0, pi / 2, 0))
        wh = bpy.context.active_object
        wh.name = "Caster"
        adopt(wh, rubber, smooth=True)
        box("Caster_Fork", (sx * 0.62, sy * 0.26, 0.085), (0.045, 0.03, 0.04), black)

# ----------------------------------------------------------------------------
# Room: wall, floor, door, plant
# ----------------------------------------------------------------------------
box("Wall", (0, 0.32, 1.6), (8, 0.1, 3.2), make_mat("Wall", (0.78, 0.76, 0.72), rough=0.9))
box("Skirting", (0, 0.265, 0.06), (8, 0.02, 0.12), make_mat("Skirting", (0.12, 0.10, 0.09), rough=0.5))

fm = bpy.data.materials.new("Floor_Tile")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
set_in(fb, ["Roughness"], 0.25)
chk = fm.node_tree.nodes.new("ShaderNodeTexChecker")
chk.inputs["Color1"].default_value = (0.72, 0.65, 0.52, 1)
chk.inputs["Color2"].default_value = (0.68, 0.61, 0.49, 1)
chk.inputs["Scale"].default_value = 3.3
fm.node_tree.links.new(chk.outputs["Color"], fb.inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, -3, 0))
fl = bpy.context.active_object
fl.name = "Floor"
adopt(fl, fm)

door_m = make_mat("Door", (0.18, 0.03, 0.04), rough=0.35)
box("Door", (-1.75, 0.255, 1.0), (0.95, 0.03, 2.0), door_m)
box("Door_Frame_L", (-2.26, 0.25, 1.05), (0.07, 0.05, 2.1), door_m)
box("Door_Frame_T", (-1.75, 0.25, 2.05), (1.1, 0.05, 0.07), door_m)

# plant
px, py = 1.30, 0.02
bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.17, radius2=0.22, depth=0.40, location=(px, py, 0.20))
pot = bpy.context.active_object
pot.name = "Pot"
adopt(pot, make_mat("Pot", (0.30, 0.07, 0.06), rough=0.4), smooth=True)
beam("Plant_Stem", (px, py, 0.35), (px, py, 1.15), 0.025, make_mat("Stem", (0.2, 0.12, 0.06)), 10)
leaf_m = make_mat("Leaf", (0.06, 0.28, 0.07), rough=0.45)
for _ in range(26):
    a = random.uniform(0, 2 * pi)
    rr = random.uniform(0.0, 0.32)
    z = random.uniform(0.55, 1.65)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1.0,
                                         location=(px + rr * math.cos(a), py + rr * math.sin(a) * 0.8 - 0.05, z))
    lf = bpy.context.active_object
    lf.name = "Leaf"
    lf.scale = (0.22, 0.20, 0.025)
    lf.rotation_euler = (random.uniform(-0.8, 0.8), random.uniform(-0.8, 0.8), random.uniform(0, 2 * pi))
    adopt(lf, leaf_m, smooth=True)

# ----------------------------------------------------------------------------
# Lights / camera
# ----------------------------------------------------------------------------
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.8, 0.82, 0.85, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8

bpy.ops.object.light_add(type='AREA', location=(0.5, -3, 3.0))
a = bpy.context.active_object
a.data.energy = 700
a.data.size = 4
a.rotation_euler = (radians(70), 0, 0)

bpy.ops.object.empty_add(location=(0.1, 0, 1.15))
tgt = bpy.context.active_object
bpy.ops.object.camera_add(location=(0.1, -3.3, 1.2))
cam = bpy.context.active_object
cam.data.lens = 35
tc = cam.constraints.new('TRACK_TO')
tc.target = tgt
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'
scene.camera = cam
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200

if USE_CYCLES:
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 96
else:
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue

print("Interactive panel built. Parent object: 'Panel_Root'.")
