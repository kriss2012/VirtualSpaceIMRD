"""
Two-seater school desk with attached bench: orange board top / seat / backrest,
perforated modesty panel, black steel frame and floor rails.   Blender 3.0+ / 4.x

HOW TO RUN: Scripting workspace -> Text > Open -> this file -> Alt+P.
            Numpad 0 = camera view, F12 = render.

Desk length is along X, the modesty panel faces -Y, the bench sits at +Y.
Everything is parented to "Desk_Root".
"""
from math import radians

import bmesh
import bpy
from mathutils import Vector

USE_CYCLES = True

# --- key dimensions (meters) ---------------------------------------------------
DESK_L = 1.20
DESK_D = 0.46
DESK_H = 0.735
BENCH_Y = 0.60           # bench centre (towards +Y)
BENCH_H = 0.43

# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene
root = bpy.data.objects.new("Desk_Root", None)
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


orange = make_mat("Orange_Board", (0.72, 0.25, 0.11), rough=0.45)
orange_steel = make_mat("Orange_Steel", (0.78, 0.30, 0.12), metallic=0.3, rough=0.4)
black = make_mat("Black_Steel", (0.012, 0.012, 0.014), metallic=0.5, rough=0.4)


def adopt(o, mat=None):
    if mat:
        o.data.materials.append(mat)
    o.parent = root
    return o


def box(name, center, size, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    return adopt(o, mat)


def perforated(name, center, w, h, cell, pitch, phase, mat, thickness=0.003):
    """Flat panel (XZ plane) with square holes cut by omitting grid cells."""
    nx, nz = round(w / cell), round(h / cell)
    bm = bmesh.new()
    verts = {}

    def V(i, j):
        if (i, j) not in verts:
            verts[(i, j)] = bm.verts.new((-w / 2 + i * w / nx, 0, -h / 2 + j * h / nz))
        return verts[(i, j)]

    for i in range(nx):
        for j in range(nz):
            if i % pitch == phase[0] and j % pitch == phase[1]:
                continue
            bm.faces.new((V(i, j), V(i + 1, j), V(i + 1, j + 1), V(i, j + 1)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.location = center
    mod = o.modifiers.new("Solidify", 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = 0
    return adopt(o, mat)


# ----------------------------------------------------------------------------
# Desk
# ----------------------------------------------------------------------------
box("Desk_Top", (0, 0, DESK_H), (DESK_L + 0.06, DESK_D, 0.03), orange)
box("Desk_Lip", (0, -DESK_D / 2 + 0.005, DESK_H - 0.025), (DESK_L + 0.03, 0.012, 0.03), black)

# modesty panel: upper orange (small round-ish holes), lower black (square holes)
perforated("Modesty_Upper", (0, -0.2, 0.605), DESK_L - 0.04, 0.21, 0.014, 4, (1, 1), orange_steel)
perforated("Modesty_Lower", (0, -0.19, 0.385), DESK_L - 0.04, 0.22, 0.02, 3, (1, 1), black)

for sx in (-1, 1):
    x = sx * (DESK_L / 2)
    # end caps on the desktop
    box(f"Top_Cap_{sx}", (x + sx * 0.04, 0, DESK_H - 0.015), (0.035, DESK_D + 0.01, 0.07), black)
    # posts (front + rear) with outer ribs
    for py in (-0.20, 0.17):
        box(f"Post_{sx}", (x, py, 0.36), (0.05, 0.10, 0.72), black)
        box(f"Post_Rib_{sx}", (x + sx * 0.032, py, 0.36), (0.014, 0.10, 0.70), black)
        box(f"Post_Rib_In_{sx}", (x - sx * 0.032, py, 0.36), (0.010, 0.10, 0.70), black)
    # solid end plate between the posts
    box(f"End_Plate_{sx}", (x, -0.015, 0.40), (0.03, 0.30, 0.60), black)
    # floor rails (run from desk front to behind the bench)
    box(f"Floor_Rail_{sx}", (x, 0.25, 0.04), (0.05, 1.0, 0.05), black)
    # bench legs
    for ly in (0.50, 0.70):
        box(f"Bench_Leg_{sx}", (x - sx * 0.04, ly, 0.21), (0.04, 0.05, 0.42), black)
    box(f"Bench_Rib_{sx}", (x - sx * 0.065, 0.60, 0.21), (0.012, 0.28, 0.40), black)
    # backrest supports
    box(f"Back_Support_{sx}", (x - sx * 0.06, 0.725, 0.66), (0.03, 0.03, 0.46), black)
    # little feet
    for fy in (-0.22, 0.72):
        box(f"Foot_{sx}", (x, fy, 0.012), (0.06, 0.06, 0.024), black)

# cross rails near the floor
box("Rail_Front", (0, -0.22, 0.06), (DESK_L, 0.04, 0.04), black)
box("Rail_Back", (0, 0.70, 0.06), (DESK_L, 0.04, 0.04), black)
box("Rail_Mid", (0, 0.18, 0.12), (DESK_L, 0.03, 0.03), black)

# ----------------------------------------------------------------------------
# Bench: seat + backrest
# ----------------------------------------------------------------------------
box("Seat", (0, BENCH_Y, BENCH_H), (DESK_L + 0.04, 0.30, 0.03), orange)
box("Backrest", (0, 0.765, 0.80), (DESK_L + 0.08, 0.022, 0.22), orange, rot=(radians(-5), 0, 0))

# ----------------------------------------------------------------------------
# Scene
# ----------------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
fl = bpy.context.active_object
fl.name = "Floor"
adopt(fl, make_mat("Floor", (0.9, 0.9, 0.9), rough=0.6))

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.95, 0.95, 0.97, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

bpy.ops.object.light_add(type='AREA', location=(-2, -3, 3.5))
a = bpy.context.active_object
a.data.energy = 600
a.data.size = 4
a.rotation_euler = (radians(55), 0, radians(-35))
bpy.ops.object.light_add(type='SUN', location=(3, -4, 6), rotation=(radians(50), 0, radians(30)))
bpy.context.active_object.data.energy = 2.0

bpy.ops.object.empty_add(location=(0.05, 0.2, 0.42))
tgt = bpy.context.active_object
bpy.ops.object.camera_add(location=(1.9, -2.5, 1.45))
cam = bpy.context.active_object
cam.data.lens = 50
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

print("School desk built. Parent object: 'Desk_Root'.")
