"""
Black / orange 26" mountain bike (front suspension fork, front disc brake,
knobby tires, spoked wheels, water bottle, kickstand) for Blender 3.0+ / 4.x

HOW TO RUN
  1. Blender -> Scripting workspace -> Text > Open -> choose this file.
  2. Press Alt+P (Run Script).
  3. Numpad 0 = camera view, F12 = render.

NOTES
  * Bike faces +X, width is along Y (drive side = -Y, facing the camera),
    up is Z.  Everything is parented to the "Bike_Root" empty.
  * Edit the point coordinates in the FRAME section to reshape the bike.
"""
import math
from math import pi, radians

import bmesh
import bpy
from mathutils import Matrix, Vector

USE_CYCLES = True
ADD_SCENE = True

# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene
root = bpy.data.objects.new("Bike_Root", None)
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
    set_in(b, ["Base Color"], (*color, 1.0))
    set_in(b, ["Metallic"], metallic)
    set_in(b, ["Roughness"], rough)
    set_in(b, ["Coat Weight", "Clearcoat"], coat)
    return m


def adopt(o, mat=None, smooth=True):
    if mat:
        o.data.materials.append(mat)
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    o.parent = root
    return o


def orient(d):
    """4x4 rotation turning +Z into direction d."""
    d = Vector(d).normalized()
    return Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()


def beam(name, p1, p2, r, mat, segs=16):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(vertices=segs, radius=r, depth=d.length,
                                        location=(p1 + p2) / 2)
    o = bpy.context.active_object
    o.name = name
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return adopt(o, mat)


def cyl_y(name, loc, r, length, mat, segs=32):
    """Cylinder whose axis is the Y axis (hubs, rotors, chainring...)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=segs, radius=r, depth=length,
                                        location=loc, rotation=(pi / 2, 0, 0))
    o = bpy.context.active_object
    o.name = name
    return adopt(o, mat)


def box(name, loc, size, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    return adopt(o, mat, smooth=False)


def mesh_object(name, bm, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    return adopt(o, mat)


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
frame_black = make_mat("Frame_Black", (0.012, 0.012, 0.014), metallic=0.6, rough=0.22, coat=1.0)
orange = make_mat("Orange", (1.0, 0.25, 0.01), metallic=0.1, rough=0.3, coat=0.5)
cyan = make_mat("Cyan", (0.0, 0.55, 0.6), metallic=0.1, rough=0.3, coat=0.5)
black_pl = make_mat("Black_Plastic", (0.01, 0.01, 0.011), rough=0.5)
rubber = make_mat("Rubber", (0.015, 0.015, 0.015), rough=0.9)
rim_mat = make_mat("Rim", (0.025, 0.025, 0.03), metallic=0.9, rough=0.3)
steel = make_mat("Steel", (0.7, 0.7, 0.72), metallic=1.0, rough=0.25)
spoke_mat = make_mat("Spokes", (0.55, 0.55, 0.58), metallic=1.0, rough=0.3)
saddle_mat = make_mat("Saddle", (0.012, 0.012, 0.012), rough=0.55)

# ----------------------------------------------------------------------------
# FRAME  (all points in the X-Z plane unless noted)
# ----------------------------------------------------------------------------
AXLE_Z = 0.35
REAR_X, FRONT_X = -0.52, 0.56
BB = Vector((0.0, 0.0, 0.30))
SEAT_TOP = Vector((-0.18, 0.0, 0.80))
HT_BOT = Vector((0.45, 0.0, 0.68))
HT_TOP = Vector((0.40, 0.0, 0.82))
u = (HT_TOP - HT_BOT).normalized()          # steering axis (pointing up)

R_TUBE = 0.0225
beam("BB_Shell", BB + Vector((0, -0.045, 0)), BB + Vector((0, 0.045, 0)), 0.024, frame_black)
beam("Seat_Tube", BB, SEAT_TOP, 0.0205, frame_black)
beam("Top_Tube", Vector((-0.17, 0, 0.77)), Vector((0.405, 0, 0.79)), 0.021, frame_black)
beam("Down_Tube", BB, Vector((0.43, 0, 0.72)), 0.028, frame_black)
beam("Head_Tube", HT_BOT, HT_TOP, 0.03, frame_black)

for s in (-1, 1):
    beam(f"Seat_Stay_{s}", Vector((-0.175, s * 0.035, 0.74)),
         Vector((REAR_X, s * 0.055, AXLE_Z)), 0.0095, frame_black)
    beam(f"Chain_Stay_{s}", Vector((0.0, s * 0.035, 0.30)),
         Vector((REAR_X, s * 0.055, AXLE_Z)), 0.0115, frame_black)

# graphic bands on the tubes (orange / cyan stripes like the decals)
dt_a, dt_b = BB, Vector((0.43, 0, 0.72))
for t0, t1, m in ((0.20, 0.34, orange), (0.34, 0.40, cyan), (0.58, 0.80, orange)):
    beam("DT_Decal", dt_a.lerp(dt_b, t0), dt_a.lerp(dt_b, t1), 0.0288, m)
tt_a, tt_b = Vector((-0.17, 0, 0.77)), Vector((0.405, 0, 0.79))
for t0, t1, m in ((0.25, 0.45, orange), (0.45, 0.50, cyan)):
    beam("TT_Decal", tt_a.lerp(tt_b, t0), tt_a.lerp(tt_b, t1), 0.0216, m)

# seat post + saddle
beam("Seat_Post", SEAT_TOP + Vector((0, 0, -0.04)), Vector((-0.215, 0, 0.95)), 0.0135, steel)
beam("Seat_Clamp", SEAT_TOP + Vector((0, 0, -0.005)), SEAT_TOP + Vector((0, 0, 0.02)), 0.0235, black_pl)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(-0.225, 0, 0.965))
sad = bpy.context.active_object
sad.name = "Saddle"
sad.scale = (0.14, 0.075, 0.03)
sad.rotation_euler = (0, radians(-4), 0)
adopt(sad, saddle_mat)
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0, location=(-0.30, 0, 0.975))
sad2 = bpy.context.active_object
sad2.name = "Saddle_Rear"
sad2.scale = (0.08, 0.085, 0.034)
adopt(sad2, saddle_mat)

# ----------------------------------------------------------------------------
# Fork (suspension), stem, handlebar
# ----------------------------------------------------------------------------
CROWN = HT_BOT - u * 0.04
FRONT_AXLE = Vector((FRONT_X, 0, AXLE_Z))
beam("Fork_Crown", CROWN + Vector((0, -0.068, 0)), CROWN + Vector((0, 0.068, 0)), 0.02, black_pl)
beam("Steerer", HT_BOT, HT_TOP + u * 0.07, 0.014, steel)

for s in (-1, 1):
    top = CROWN + Vector((0, s * 0.065, 0))
    bot = Vector((FRONT_X, s * 0.052, AXLE_Z))
    mid = top.lerp(bot, 0.48)
    beam(f"Stanchion_{s}", top, mid, 0.0145, steel)           # upper tube (chrome)
    beam(f"Fork_Lower_{s}", mid - (bot - top) * 0.04, bot, 0.021, black_pl)
    beam(f"Fork_Decal_{s}", top.lerp(bot, 0.62), top.lerp(bot, 0.80), 0.0215, orange)

T = HT_TOP + u * 0.095
BAR_C = T + Vector((0.075, 0, 0.012))
beam("Stem", T, BAR_C, 0.017, black_pl)
beam("Stem_Clamp", BAR_C + Vector((0, -0.03, 0)), BAR_C + Vector((0, 0.03, 0)), 0.02, black_pl)
for s in (-1, 1):
    beam(f"Bar_Mid_{s}", BAR_C + Vector((0, s * 0.03, 0)), BAR_C + Vector((-0.01, s * 0.14, 0)), 0.0115, black_pl)
    beam(f"Bar_End_{s}", BAR_C + Vector((-0.01, s * 0.14, 0)), BAR_C + Vector((-0.045, s * 0.31, 0.005)), 0.0115, black_pl)
    beam(f"Grip_{s}", BAR_C + Vector((-0.037, s * 0.22, 0.004)), BAR_C + Vector((-0.045, s * 0.31, 0.005)), 0.0165, black_pl)
    beam(f"Brake_Lever_{s}", BAR_C + Vector((-0.03, s * 0.20, 0.004)),
         BAR_C + Vector((0.07, s * 0.20, -0.012)), 0.0055, steel)
    beam(f"Lever_Mount_{s}", BAR_C + Vector((-0.032, s * 0.18, 0.004)),
         BAR_C + Vector((-0.032, s * 0.215, 0.004)), 0.014, black_pl)

# ----------------------------------------------------------------------------
# Wheels
# ----------------------------------------------------------------------------
TIRE_R, TIRE_r = 0.31, 0.042          # outer radius = 0.352
RIM_R, RIM_r = 0.283, 0.014


def make_wheel(tag, cx, disc_side=None):
    cz = AXLE_Z
    # tire + rim (torus around Y axis)
    bpy.ops.mesh.primitive_torus_add(major_radius=TIRE_R, minor_radius=TIRE_r,
                                     major_segments=72, minor_segments=14,
                                     location=(cx, 0, cz), rotation=(pi / 2, 0, 0))
    t = bpy.context.active_object
    t.name = f"{tag}_Tire"
    adopt(t, rubber)
    bpy.ops.mesh.primitive_torus_add(major_radius=RIM_R, minor_radius=RIM_r,
                                     major_segments=72, minor_segments=10,
                                     location=(cx, 0, cz), rotation=(pi / 2, 0, 0))
    rm = bpy.context.active_object
    rm.name = f"{tag}_Rim"
    adopt(rm, rim_mat)

    # tread blocks (two staggered rows) merged into one mesh
    bm = bmesh.new()
    N = 64
    for row, dy in enumerate((-0.021, 0.021)):
        for i in range(N):
            a = 2 * pi * (i + 0.5 * row) / N
            pos = Vector((cx + (TIRE_R + TIRE_r + 0.002) * math.cos(a), dy,
                          cz + (TIRE_R + TIRE_r + 0.002) * math.sin(a)))
            M = (Matrix.Translation(pos) @ Matrix.Rotation(-a, 4, 'Y')
                 @ Matrix.Diagonal(Vector((0.014, 0.030, 0.026, 1.0))))
            bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    mesh_object(f"{tag}_Tread", bm, rubber)

    # spokes (36, crossed) merged into one mesh
    bm = bmesh.new()
    for i in range(36):
        a = 2 * pi * i / 36
        side = 1 if i % 2 == 0 else -1
        a2 = a + side * 0.33
        p1 = Vector((cx + 0.03 * math.cos(a), side * 0.028, cz + 0.03 * math.sin(a)))
        p2 = Vector((cx + RIM_R * math.cos(a2), 0.0, cz + RIM_R * math.sin(a2)))
        d = p2 - p1
        M = Matrix.Translation((p1 + p2) / 2) @ orient(d)
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=4,
                              radius1=0.0016, radius2=0.0016, depth=d.length, matrix=M)
    mesh_object(f"{tag}_Spokes", bm, spoke_mat)

    # hub + flanges
    cyl_y(f"{tag}_Hub", (cx, 0, cz), 0.022, 0.09, black_pl, 24)
    for s in (-1, 1):
        cyl_y(f"{tag}_Flange_{s}", (cx, s * 0.03, cz), 0.034, 0.006, steel, 24)

    # orange rim stickers
    for a in (0.0, 2 * pi / 3, 4 * pi / 3):
        for s in (-1, 1):
            pos = Vector((cx + RIM_R * math.cos(a), s * (RIM_r + 0.001), cz + RIM_R * math.sin(a)))
            M = Matrix.Rotation(-a, 4, 'Y')
            o = box(f"{tag}_Sticker", pos, (0.016, 0.003, 0.07), orange)
            o.rotation_mode = 'QUATERNION'
            o.rotation_quaternion = M.to_quaternion()

    # disc brake rotor + caliper
    if disc_side is not None:
        y = disc_side * 0.042
        cyl_y(f"{tag}_Rotor", (cx, y, cz), 0.08, 0.003, steel, 48)
        cyl_y(f"{tag}_RotorHub", (cx, y, cz), 0.03, 0.005, black_pl, 24)
        box(f"{tag}_Caliper", (cx - 0.045, y, cz + 0.06), (0.05, 0.02, 0.045), orange,
            rot=(0, radians(-35), 0))


make_wheel("Rear", REAR_X)
make_wheel("Front", FRONT_X, disc_side=-1)

# ----------------------------------------------------------------------------
# Drivetrain
# ----------------------------------------------------------------------------
YD = -0.06                                   # drive-side plane
cyl_y("Chainring", (BB.x, YD, BB.z), 0.09, 0.006, black_pl, 48)
cyl_y("Chainring_Inner", (BB.x, YD - 0.004, BB.z), 0.045, 0.004, steel, 24)
cyl_y("Cassette", (REAR_X, -0.045, AXLE_Z), 0.062, 0.03, steel, 32)
for z_off, z_off2 in ((0.09, 0.062), (-0.09, -0.062)):
    beam("Chain", Vector((BB.x, YD, BB.z + z_off)), Vector((REAR_X, YD, AXLE_Z + z_off2)), 0.005, black_pl, 8)

# crank arms + pedals
cr_r = Vector((0.04, -0.075, 0.14))          # right crank (down)
cr_l = Vector((-0.04, 0.075, 0.46))          # left crank (up)
beam("Crank_R", Vector((0, -0.075, 0.30)), cr_r, 0.012, black_pl)
beam("Crank_L", Vector((0, 0.075, 0.30)), cr_l, 0.012, black_pl)
beam("Spindle", Vector((0, -0.075, 0.30)), Vector((0, 0.075, 0.30)), 0.009, steel)
box("Pedal_R", cr_r + Vector((0, -0.05, 0)), (0.10, 0.09, 0.02), black_pl)
box("Pedal_L", cr_l + Vector((0, 0.05, 0)), (0.10, 0.09, 0.02), black_pl)

# kickstand
beam("Kickstand", Vector((-0.27, -0.03, 0.285)), Vector((-0.31, -0.10, 0.005)), 0.007, black_pl, 8)
box("Kickstand_Foot", (-0.31, -0.10, 0.004), (0.035, 0.03, 0.01), black_pl)

# water bottle + cage
d0, d1 = BB, Vector((0.43, 0, 0.72))
b0, b1 = d0.lerp(d1, 0.40) + Vector((0, -0.05, 0.0)), d0.lerp(d1, 0.78) + Vector((0, -0.05, 0.0))
beam("Bottle", b0, b1, 0.034, black_pl, 24)
beam("Bottle_Cap", b1, b1 + (b1 - b0).normalized() * 0.03, 0.017, orange, 16)
beam("Cage", b0.lerp(b1, 0.15), b0.lerp(b1, 0.6), 0.036, steel, 8)

# ----------------------------------------------------------------------------
# Scene: wooden floor, warm sky, lights, camera
# ----------------------------------------------------------------------------
if ADD_SCENE:
    floor_m = bpy.data.materials.new("Wood_Floor")
    floor_m.use_nodes = True
    nt = floor_m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    set_in(bsdf, ["Roughness"], 0.4)
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.inputs["Color1"].default_value = (0.42, 0.22, 0.11, 1)
    brick.inputs["Color2"].default_value = (0.55, 0.30, 0.15, 1)
    brick.inputs["Mortar"].default_value = (0.08, 0.04, 0.02, 1)
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = 0.004
    brick.inputs["Brick Width"].default_value = 1.2
    brick.inputs["Row Height"].default_value = 0.18
    nt.links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.data.materials.append(floor_m)

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1.0, 0.75, 0.4, 1)     # warm hazy sky
    bg.inputs["Strength"].default_value = 1.0

    bpy.ops.object.light_add(type='SUN', location=(4, -4, 6), rotation=(radians(55), 0, radians(30)))
    sun = bpy.context.active_object
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.88, 0.65)
    bpy.ops.object.light_add(type='AREA', location=(-2, -3, 3))
    fill = bpy.context.active_object
    fill.data.energy = 250
    fill.data.size = 3
    fill.rotation_euler = (radians(60), 0, radians(-30))

    bpy.ops.object.empty_add(location=(0.0, 0, 0.42))
    tgt = bpy.context.active_object
    tgt.name = "Cam_Target"
    bpy.ops.object.camera_add(location=(2.0, -2.7, 0.8))
    cam = bpy.context.active_object
    cam.data.lens = 50
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt
    c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'
    scene.camera = cam
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1440

    if USE_CYCLES:
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 128
    else:
        for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            try:
                scene.render.engine = eng
                break
            except TypeError:
                continue

print("Mountain bike built. Parent object: 'Bike_Root'.")
