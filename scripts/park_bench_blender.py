"""
Park bench: black cast-iron legs + red-brown wooden slats (3 seat, 2 back)
For Blender 3.0+ / 4.x

HOW TO RUN
  Blender -> Scripting workspace -> Text > Open -> this file -> Alt+P.
  Numpad 0 = camera view, F12 = render.

Bench length runs along X, front of the seat faces -Y, up is Z (units = meters).
Everything is parented to the "Bench_Root" empty.
"""
import math
from math import pi, radians

import bmesh
import bpy
from mathutils import Matrix, Vector

# ----------------------------------------------------------------------------
# Parameters (meters)
# ----------------------------------------------------------------------------
BENCH_LEN = 1.80
LEG_X = 0.78            # distance of the leg frames from the centre
SEAT_Z = 0.45           # seat height
SEAT_SLAT_W = 0.12
SEAT_GAP = 0.012
SLAT_T = 0.032
BACK_TILT = 12          # degrees
BACK_SLAT_W = 0.13
USE_CYCLES = True

# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene
root = bpy.data.objects.new("Bench_Root", None)
scene.collection.objects.link(root)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def set_in(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return


def make_mat(name, color, metallic=0.0, rough=0.5, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    set_in(b, ["Base Color"], (*color, 1))
    set_in(b, ["Metallic"], metallic)
    set_in(b, ["Roughness"], rough)
    set_in(b, ["Coat Weight", "Clearcoat"], coat)
    return m


def make_wood():
    m = bpy.data.materials.new("Mahogany")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    set_in(b, ["Roughness"], 0.32)
    set_in(b, ["Coat Weight", "Clearcoat"], 0.4)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (2.0, 60.0, 60.0)   # stretched along X = grain
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.40, 0.11, 0.05, 1)
    ramp.color_ramp.elements[1].color = (0.58, 0.20, 0.09, 1)
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


iron = make_mat("Cast_Iron", (0.012, 0.012, 0.014), metallic=0.7, rough=0.45)
chrome = make_mat("Chrome", (0.85, 0.85, 0.88), metallic=1.0, rough=0.12)
wood = make_wood()


def adopt(o, mat=None):
    if mat:
        o.data.materials.append(mat)
    o.parent = root
    return o


def solid_box(name, center, size, mat, rot=(0, 0, 0), bevel=0.008):
    """Real-size box mesh (so the Bevel modifier isn't distorted by scale)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal(Vector((*size, 1.0))))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.location = center
    o.rotation_euler = rot
    if bevel:
        mod = o.modifiers.new("Bevel", 'BEVEL')
        mod.width = bevel
        mod.segments = 3
    return adopt(o, mat)


def tube(name, pts, radii, mat):
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    cd.bevel_depth = 1.0
    cd.bevel_resolution = 4
    cd.fill_mode = 'FULL'
    cd.use_fill_caps = True
    sp = cd.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, pt, r in zip(sp.points, pts, radii):
        p.co = (*pt, 1.0)
        p.radius = r
    cd.materials.append(mat)
    o = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(o)
    o.parent = root
    return o


def sphere(name, loc, r, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (1, 1, 0.6)
    bpy.ops.object.shade_smooth()
    return adopt(o, mat)


# ----------------------------------------------------------------------------
# Wooden slats
# ----------------------------------------------------------------------------
tilt = radians(BACK_TILT)
slope = math.tan(tilt)

# seat: three slats along X
step = SEAT_SLAT_W + SEAT_GAP
seat_ys = [-step, 0.0, step]
for i, y in enumerate(seat_ys):
    solid_box(f"Seat_Slat_{i}", (0, y, SEAT_Z + SLAT_T / 2),
              (BENCH_LEN, SEAT_SLAT_W, SLAT_T), wood)
    for sx in (-1, 1):                                    # chrome bolts
        sphere(f"Seat_Bolt", (sx * (LEG_X + 0.04), y, SEAT_Z + SLAT_T + 0.002), 0.0095, chrome)

# backrest: two slats, leaning back
back_base_y = seat_ys[-1] + SEAT_SLAT_W / 2 + 0.02
for i, z in enumerate((SEAT_Z + 0.14, SEAT_Z + 0.29)):
    y = back_base_y + (z - SEAT_Z) * slope
    solid_box(f"Back_Slat_{i}", (0, y, z), (BENCH_LEN + 0.04, SLAT_T, BACK_SLAT_W), wood,
              rot=(-tilt, 0, 0))
    for sx in (-1, 1):
        sphere("Back_Bolt", (sx * (LEG_X + 0.01 + 0.02), y - SLAT_T / 2 - 0.001, z), 0.0095, chrome)

# ----------------------------------------------------------------------------
# Cast-iron end frames
# ----------------------------------------------------------------------------
def leg_points(y_top, y_foot, z_top, n=14, power=2.2):
    pts = []
    for k in range(n + 1):
        t = k / n
        pts.append((None, y_top + (y_foot - y_top) * t ** power, z_top * (1 - t) + 0.012 * t))
    return pts


for sx in (-1, 1):
    x = sx * LEG_X
    z_top = SEAT_Z - 0.01
    # front leg (flares forward)
    fl = [(x, y, z) for (_, y, z) in leg_points(-0.16, -0.30, z_top)]
    tube(f"Front_Leg_{sx}", fl, [0.026 - 0.011 * i / 14 for i in range(15)], iron)
    # rear leg (flares backward)
    rl = [(x, y, z) for (_, y, z) in leg_points(0.17, 0.31, z_top)]
    tube(f"Rear_Leg_{sx}", rl, [0.026 - 0.011 * i / 14 for i in range(15)], iron)

    # cross bracket under the seat (flat cast piece)
    solid_box(f"Bracket_{sx}", (x, 0.005, SEAT_Z - 0.03), (0.055, 0.46, 0.05), iron, bevel=0.01)
    # backrest support post
    top_z = SEAT_Z + 0.37
    bottom = (x, 0.17, SEAT_Z - 0.02)
    top = (x, back_base_y + (top_z - SEAT_Z) * slope - SLAT_T / 2 - 0.004, top_z)
    mid = tuple((a + b) / 2 for a, b in zip(bottom, top))
    tube(f"Back_Post_{sx}", [bottom, mid, top], [0.024, 0.021, 0.018], iron)

    # foot plates
    for fy in (-0.30, 0.31):
        solid_box(f"Foot_{sx}", (x, fy, 0.006), (0.12, 0.085, 0.012), iron, bevel=0.003)
        sphere("Foot_Bolt", (x, fy, 0.014), 0.008, chrome)

# ----------------------------------------------------------------------------
# Scene
# ----------------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"
gm = make_mat("Ground", (0.85, 0.85, 0.86), rough=0.8)
ground.data.materials.append(gm)

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.9, 0.92, 0.95, 1)
bg.inputs["Strength"].default_value = 1.0

bpy.ops.object.light_add(type='SUN', location=(4, -5, 8), rotation=(radians(50), 0, radians(30)))
bpy.context.active_object.data.energy = 3.5

bpy.ops.object.empty_add(location=(0, 0, 0.4))
tgt = bpy.context.active_object
bpy.ops.object.camera_add(location=(3.0, -3.6, 1.7))
cam = bpy.context.active_object
cam.data.lens = 45
c = cam.constraints.new('TRACK_TO')
c.target = tgt
c.track_axis = 'TRACK_NEGATIVE_Z'
c.up_axis = 'UP_Y'
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

print("Park bench built. Parent object: 'Bench_Root'.")
