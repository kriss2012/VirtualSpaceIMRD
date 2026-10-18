"""
Library bookshelf wall: 4 bays, oak pilasters, 5 shelves each, hundreds of books,
panelled base cabinets, wood-plank floor.            Blender 3.0+ / 4.x

HOW TO RUN: Scripting workspace -> Text > Open -> this file -> Alt+P.
            Numpad 0 = camera view, F12 = render.

Layout (meters): shelves run along X, front of the shelves faces -Y, up is Z,
the wall is at Y = DEPTH.  Everything is parented to "Bookshelf_Root".
"""
import random
from math import radians

import bmesh
import bpy
from mathutils import Matrix, Vector

SEED = 11
N_BAYS = 4
BAY_W = 1.20            # clear width of one bay
PILASTER_W = 0.12
DEPTH = 0.34
BASE_H = 0.45           # height of the cabinet base
N_ROWS = 5              # shelves per bay
ROW_H = 0.43
SHELF_T = 0.03
USE_CYCLES = True

random.seed(SEED)
TOTAL_W = N_BAYS * (BAY_W + PILASTER_W) + PILASTER_W
TOP_Z = BASE_H + N_ROWS * ROW_H          # top of the highest shelf board
H = TOP_Z + 0.15                         # overall unit height

# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene
root = bpy.data.objects.new("Bookshelf_Root", None)
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


def make_oak(name, dark, light, rough=0.4):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    set_in(b, ["Roughness"], rough)
    geo = nt.nodes.new("ShaderNodeNewGeometry")           # world position -> grain
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (2.0, 28.0, 28.0)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 4.0
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = (*dark, 1)
    rp.color_ramp.elements[1].color = (*light, 1)
    nt.links.new(geo.outputs["Position"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"])
    nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
    return m


oak = make_oak("Oak", (0.30, 0.17, 0.07), (0.50, 0.30, 0.13))
oak_dark = make_oak("Oak_Dark", (0.18, 0.09, 0.04), (0.30, 0.16, 0.07))


def adopt(o, mat=None, smooth=False):
    if mat:
        o.data.materials.append(mat)
    if smooth and o.type == 'MESH':
        for p in o.data.polygons:
            p.use_smooth = True
    o.parent = root
    return o


def box(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    return adopt(o, mat)


# ----------------------------------------------------------------------------
# Cabinet carcass
# ----------------------------------------------------------------------------
# back panel
box("Back_Panel", (TOTAL_W / 2, DEPTH - 0.01, H / 2), (TOTAL_W, 0.02, H), oak_dark)
# pilasters (with plinth block, capital and three reeds on the face)
for k in range(N_BAYS + 1):
    cx = k * (BAY_W + PILASTER_W) + PILASTER_W / 2
    box(f"Pilaster_{k}", (cx, DEPTH / 2 - 0.015, H / 2), (PILASTER_W, DEPTH + 0.03, H), oak)
    box(f"Plinth_{k}", (cx, DEPTH / 2 - 0.025, 0.14), (PILASTER_W + 0.03, DEPTH + 0.05, 0.28), oak)
    box(f"Capital_{k}", (cx, DEPTH / 2 - 0.025, TOP_Z + 0.06), (PILASTER_W + 0.03, DEPTH + 0.05, 0.1), oak)
    for dx in (-0.032, 0.0, 0.032):
        box(f"Reed_{k}", (cx + dx, -0.033, (0.28 + TOP_Z) / 2), (0.014, 0.01, TOP_Z - 0.35), oak_dark)

# top rail
box("Top_Rail", (TOTAL_W / 2, DEPTH / 2, TOP_Z + 0.075), (TOTAL_W, DEPTH, 0.15), oak)

# ----------------------------------------------------------------------------
# Bays: shelves, base panels, books
# ----------------------------------------------------------------------------
PALETTE = [
    (0.25, 0.10, 0.04), (0.40, 0.20, 0.08), (0.10, 0.05, 0.03), (0.35, 0.04, 0.03),
    (0.05, 0.15, 0.07), (0.10, 0.25, 0.12), (0.05, 0.10, 0.25), (0.10, 0.20, 0.40),
    (0.70, 0.62, 0.45), (0.50, 0.45, 0.35), (0.80, 0.78, 0.70), (0.03, 0.03, 0.03),
    (0.55, 0.30, 0.10), (0.60, 0.50, 0.30), (0.20, 0.18, 0.15), (0.45, 0.08, 0.10),
]

bm = bmesh.new()
vert_color = {}


def add_book(cx, cz, w, d, h, tilt, col):
    cy = 0.05 + d / 2 + random.uniform(0.0, 0.03)
    M = (Matrix.Translation((cx, cy, cz)) @ Matrix.Rotation(tilt, 4, 'Y')
         @ Matrix.Diagonal(Vector((w, d, h, 1.0))))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    for v in res["verts"]:
        vert_color[v] = col


for i in range(N_BAYS):
    xl = i * (BAY_W + PILASTER_W) + PILASTER_W
    xc = xl + BAY_W / 2

    # base cabinet: plinth strip, front panel with raised centre panel
    box("Base_Front", (xc, 0.015, (BASE_H + 0.05) / 2), (BAY_W, 0.03, BASE_H - 0.05), oak)
    box("Base_Panel", (xc, -0.004, BASE_H / 2 + 0.03), (BAY_W - 0.22, 0.014, BASE_H - 0.22), oak_dark)
    box("Base_Foot", (xc, 0.0, 0.025), (BAY_W, 0.045, 0.05), oak)

    # shelf boards: k = 0 is the cabinet top, 1..N_ROWS the shelves above it
    for k in range(N_ROWS + 1):
        zt = BASE_H + k * ROW_H
        box(f"Shelf_{i}_{k}", (xc, (DEPTH - 0.02) / 2, zt - SHELF_T / 2), (BAY_W, DEPTH - 0.02, SHELF_T), oak)
        box(f"Shelf_Edge_{i}_{k}", (xc, -0.004, zt - SHELF_T / 2), (BAY_W, 0.012, SHELF_T + 0.012), oak_dark)

    # books on shelves 0..N_ROWS-1
    for k in range(N_ROWS):
        z0 = BASE_H + k * ROW_H
        avail = ROW_H - SHELF_T
        x = xl + 0.015
        x_end = xl + BAY_W - 0.015
        while x < x_end - 0.03:
            if random.random() < 0.05:                   # small gap
                x += random.uniform(0.02, 0.05)
                continue
            w = random.uniform(0.018, 0.052)
            if x + w > x_end:
                break
            h = random.uniform(0.62, 0.93) * avail
            d = random.uniform(0.17, 0.24)
            col = random.choice(PALETTE)
            j = random.uniform(-0.04, 0.04)
            col = (max(0.0, col[0] + j), max(0.0, col[1] + j), max(0.0, col[2] + j), 1.0)
            tilt = 0.0
            if random.random() < 0.04 and w < 0.035:     # a leaning book
                tilt = radians(random.choice((-1, 1)) * random.uniform(6, 14))
            add_book(x + w / 2, z0 + h / 2 * (1 if tilt == 0 else 1.0), w, d, h, tilt, col)
            x += w + 0.002

bm.verts.index_update()
colors = [None] * len(bm.verts)
for v, c in vert_color.items():
    colors[v.index] = c
mesh = bpy.data.meshes.new("Books")
bm.to_mesh(mesh)
bm.free()
try:
    attr = mesh.color_attributes.new("Col", 'FLOAT_COLOR', 'CORNER')
    for lp in mesh.loops:
        attr.data[lp.index].color = colors[lp.vertex_index]
except Exception:
    vc = mesh.vertex_colors.new(name="Col")
    for lp in mesh.loops:
        vc.data[lp.index].color = colors[lp.vertex_index]

bmat = bpy.data.materials.new("Books_Mat")
bmat.use_nodes = True
bb = bmat.node_tree.nodes["Principled BSDF"]
set_in(bb, ["Roughness"], 0.55)
vcn = bmat.node_tree.nodes.new("ShaderNodeVertexColor")
vcn.layer_name = "Col"
bmat.node_tree.links.new(vcn.outputs["Color"], bb.inputs["Base Color"])
mesh.materials.append(bmat)
books = bpy.data.objects.new("Books", mesh)
scene.collection.objects.link(books)
books.parent = root

# ----------------------------------------------------------------------------
# Room: floor, wall, ceiling
# ----------------------------------------------------------------------------
fm = bpy.data.materials.new("Floor_Planks")
fm.use_nodes = True
fnt = fm.node_tree
fb = fnt.nodes["Principled BSDF"]
set_in(fb, ["Roughness"], 0.35)
br = fnt.nodes.new("ShaderNodeTexBrick")
br.inputs["Color1"].default_value = (0.42, 0.30, 0.20, 1)
br.inputs["Color2"].default_value = (0.50, 0.37, 0.25, 1)
br.inputs["Mortar"].default_value = (0.20, 0.13, 0.08, 1)
br.inputs["Scale"].default_value = 1.0
br.inputs["Mortar Size"].default_value = 0.003
br.inputs["Brick Width"].default_value = 1.4
br.inputs["Row Height"].default_value = 0.14
fnt.links.new(br.outputs["Color"], fb.inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=30, location=(TOTAL_W / 2, -6, 0))
fl = bpy.context.active_object
fl.name = "Floor"
adopt(fl, fm)

wall_m = make_mat("Wall", (0.12, 0.10, 0.09), rough=0.9)
box("Wall_Left", (-0.6, 2.0, 2.0), (0.1, 6, 4.2), wall_m)
box("Wall_Right", (TOTAL_W + 0.6, 2.0, 2.0), (0.1, 6, 4.2), wall_m)
bpy.ops.mesh.primitive_plane_add(size=30, location=(TOTAL_W / 2, -6, H + 0.55))
ce = bpy.context.active_object
ce.name = "Ceiling"
adopt(ce, make_mat("Ceiling", (0.10, 0.08, 0.07), rough=0.9))

# ----------------------------------------------------------------------------
# Lights, camera, render
# ----------------------------------------------------------------------------
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.04, 0.035, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6

for x in (TOTAL_W * 0.25, TOTAL_W * 0.75):
    bpy.ops.object.light_add(type='AREA', location=(x, -2.2, H + 0.3))
    a = bpy.context.active_object
    a.data.energy = 450
    a.data.size = 3.0
    a.rotation_euler = (radians(25), 0, 0)
    a.data.color = (1.0, 0.92, 0.8)

bpy.ops.object.empty_add(location=(TOTAL_W / 2, 0, 1.3))
tgt = bpy.context.active_object
bpy.ops.object.camera_add(location=(TOTAL_W / 2, -4.3, 1.35))
cam = bpy.context.active_object
cam.data.lens = 28
tc = cam.constraints.new('TRACK_TO')
tc.target = tgt
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'
scene.camera = cam
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000

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

print("Bookshelf wall built. Parent object: 'Bookshelf_Root'.")
