"""
Badminton court built from the dimensions in the diagram (feet -> meters)
For Blender 3.0+ / 4.x

HOW TO RUN
  Blender -> Scripting workspace -> Text > Open -> this file -> Alt+P.
  Numpad 0 = camera view, F12 = render.

Court length runs along X, the net stands at X = 0, width along Y, up is Z.
Everything is parented to the "Court_Root" empty.

Dimensions used (from the diagram)
  court 44 ft x 20 ft (doubles)     singles sidelines 1.5 ft inside doubles
  short service line 6.5 ft from net   long service (doubles) 2.5 ft from back line
  net: 5 ft at centre, 5.08 ft at posts, 2.5 ft deep
"""
from math import radians

import bmesh
import bpy
from mathutils import Matrix, Vector

FT = 0.3048
USE_CYCLES = True

# --- court geometry (meters) -------------------------------------------------
HALF_L = 22.0 * FT            # 44 ft long  -> 22 ft each side of the net
HALF_W = 10.0 * FT            # 20 ft wide
SINGLES_HALF_W = 8.5 * FT     # singles court is 17 ft wide
SHORT_SERVICE = 6.5 * FT
LONG_SERVICE_DBL = HALF_L - 2.5 * FT
NET_CENTER_H = 5.0 * FT
POST_H = 5.08 * FT
NET_DEPTH = 2.5 * FT
LINE_W = 0.04

GREEN_MARGIN = 1.2 * FT * 2   # green PU surface beyond the lines
WOOD_MARGIN = 3.0 * FT        # wooden surround beyond the green
FLOOR_T = 0.05

# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene
root = bpy.data.objects.new("Court_Root", None)
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


def adopt(o, mat=None):
    if mat:
        o.data.materials.append(mat)
    o.parent = root
    return o


def box(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    return adopt(o, mat)


# --- materials ---------------------------------------------------------------
wood_m = bpy.data.materials.new("Wood_Floor")
wood_m.use_nodes = True
nt = wood_m.node_tree
wb = nt.nodes["Principled BSDF"]
set_in(wb, ["Roughness"], 0.35)
brick = nt.nodes.new("ShaderNodeTexBrick")
brick.inputs["Color1"].default_value = (0.70, 0.40, 0.14, 1)
brick.inputs["Color2"].default_value = (0.80, 0.50, 0.20, 1)
brick.inputs["Mortar"].default_value = (0.45, 0.25, 0.08, 1)
brick.inputs["Scale"].default_value = 1.0
brick.inputs["Mortar Size"].default_value = 0.003
brick.inputs["Brick Width"].default_value = 1.4
brick.inputs["Row Height"].default_value = 0.12
nt.links.new(brick.outputs["Color"], wb.inputs["Base Color"])

green_m = make_mat("Court_Green", (0.02, 0.30, 0.09), rough=0.5)
line_m = make_mat("Line_White", (0.95, 0.95, 0.95), rough=0.4)
post_m = make_mat("Post_Yellow", (0.95, 0.75, 0.05), metallic=0.2, rough=0.35)
dark_m = make_mat("Dark", (0.03, 0.03, 0.03), rough=0.6)
net_m = make_mat("Net_White", (0.95, 0.95, 0.95), rough=0.7)

# --- floor: wood slab + green court surface ---------------------------------
green_hl = HALF_L + GREEN_MARGIN
green_hw = HALF_W + GREEN_MARGIN
wood_hl = green_hl + WOOD_MARGIN
wood_hw = green_hw + WOOD_MARGIN

box("Wood_Floor", (0, 0, -FLOOR_T / 2), (wood_hl * 2, wood_hw * 2, FLOOR_T), wood_m)
box("Green_Court", (0, 0, 0.002), (green_hl * 2, green_hw * 2, 0.004), green_m)

# --- court lines -------------------------------------------------------------
def line(name, x1, y1, x2, y2):
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    sx = max(abs(x2 - x1), LINE_W)
    sy = max(abs(y2 - y1), LINE_W)
    box(name, (cx, cy, 0.005), (sx, sy, 0.002), line_m)


# outer (doubles) boundary
line("Back_Line_A", -HALF_L, -HALF_W, -HALF_L, HALF_W)
line("Back_Line_B", HALF_L, -HALF_W, HALF_L, HALF_W)
for s in (-1, 1):
    line("Doubles_Side", -HALF_L, s * HALF_W, HALF_L, s * HALF_W)
    line("Singles_Side", -HALF_L, s * SINGLES_HALF_W, HALF_L, s * SINGLES_HALF_W)
    # short service lines
    line("Short_Service", s * SHORT_SERVICE, -HALF_W, s * SHORT_SERVICE, HALF_W)
    # doubles long service lines
    line("Long_Service_Dbl", s * LONG_SERVICE_DBL, -HALF_W, s * LONG_SERVICE_DBL, HALF_W)
    # centre lines (short service line to back line)
    line("Center_Line", s * SHORT_SERVICE, 0, s * HALF_L, 0)

# --- net + posts -------------------------------------------------------------
post_y = HALF_W
for s in (-1, 1):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.03, depth=POST_H,
                                        location=(0, s * post_y, POST_H / 2))
    p = bpy.context.active_object
    p.name = "Net_Post"
    bpy.ops.object.shade_smooth()
    adopt(p, post_m)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.16, depth=0.03,
                                        location=(0, s * post_y, 0.019))
    base = bpy.context.active_object
    base.name = "Post_Base"
    bpy.ops.object.shade_smooth()
    adopt(base, dark_m)

# net mesh (grid in the YZ plane, shown as thin netting via a Wireframe modifier)
nx, nz = 61, 9
net_w = 2 * post_y
z_bot = NET_CENTER_H - NET_DEPTH
bm = bmesh.new()
grid = []
for j in range(nz):
    row = []
    for i in range(nx):
        y = -post_y + net_w * i / (nx - 1)
        z = z_bot + NET_DEPTH * j / (nz - 1)
        # small lift towards the posts (net is 5.08 ft there, 5 ft at centre)
        z += (POST_H - NET_CENTER_H) * (abs(y) / post_y) ** 2 * (j / (nz - 1))
        row.append(bm.verts.new((0, y, z)))
    grid.append(row)
for j in range(nz - 1):
    for i in range(nx - 1):
        bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
me = bpy.data.meshes.new("Net")
bm.to_mesh(me)
bm.free()
net = bpy.data.objects.new("Net", me)
scene.collection.objects.link(net)
wf = net.modifiers.new("Wireframe", 'WIREFRAME')
wf.thickness = 0.004
adopt(net, net_m)

# white tape on top and bottom of the net
for j, (z, h) in enumerate(((NET_CENTER_H - 0.02, 0.05), (z_bot + 0.005, 0.015))):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
    t = bpy.context.active_object
    t.name = "Net_Tape"
    t.scale = (0.012, net_w, h)
    adopt(t, line_m)

# --- scene: sky, lights, camera ---------------------------------------------
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.93, 0.95, 0.98, 1)
bg.inputs["Strength"].default_value = 1.0

bpy.ops.object.light_add(type='SUN', location=(-6, -8, 12), rotation=(radians(45), 0, radians(-30)))
bpy.context.active_object.data.energy = 3.5

bpy.ops.object.empty_add(location=(0, 0, 0.6))
tgt = bpy.context.active_object
tgt.name = "Cam_Target"
bpy.ops.object.camera_add(location=(-10.5, -11.5, 8.5))
cam = bpy.context.active_object
cam.data.lens = 32
c = cam.constraints.new('TRACK_TO')
c.target = tgt
c.track_axis = 'TRACK_NEGATIVE_Z'
c.up_axis = 'UP_Y'
scene.camera = cam
scene.render.resolution_x = 1600
scene.render.resolution_y = 900

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

print("Badminton court built. Parent object: 'Court_Root'.")
