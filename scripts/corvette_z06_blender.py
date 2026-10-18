"""
Stylized red mid-engine supercar (Corvette Z06 look) for Blender 3.x / 4.x

HOW TO RUN
  1. Open Blender -> Scripting workspace -> Text > Open -> pick this file.
  2. Press  Alt+P  (Run Script).
  3. Press Numpad 0 for camera view, or F12 to render.

NOTES
  * Car faces +X, width is along Y, up is Z (about 4.8 m long).
  * Body = lofted superellipse cross-sections + subdivision + boolean wheel arches.
  * Tweak the BODY / CABIN station tables below to reshape the car.
"""
import math
from math import pi, radians

import bmesh
import bpy

USE_CYCLES = True          # False -> EEVEE
RENDER_SCENE = True        # add ground, lights, camera, world

# ----------------------------------------------------------------------------
# Scene cleanup
# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

scene = bpy.context.scene
root = bpy.data.objects.new("Car_Root", None)
scene.collection.objects.link(root)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def set_in(node, names, value):
    """Set the first matching input name (handles Blender version differences)."""
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return


def make_mat(name, color, metallic=0.0, rough=0.5, coat=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    set_in(b, ["Base Color"], (*color, 1.0))
    set_in(b, ["Metallic"], metallic)
    set_in(b, ["Roughness"], rough)
    set_in(b, ["Coat Weight", "Clearcoat"], coat)
    set_in(b, ["Coat Roughness", "Clearcoat Roughness"], 0.03)
    if emit:
        set_in(b, ["Emission Color", "Emission"], (*emit, 1.0))
        set_in(b, ["Emission Strength"], emit_strength)
    return m


def parent(obj):
    obj.parent = root
    return obj


def add_cyl(name, r, depth, loc, rot=(pi / 2, 0, 0), mat=None, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    if mat:
        o.data.materials.append(mat)
    return parent(o)


def add_box(name, loc, size, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.data.materials.append(mat)
    return parent(o)


def sgnpow(v, p):
    return math.copysign(abs(v) ** p, v)


def loft(name, stations, mats, M=20, n=2.8):
    """
    Build a closed mesh by lofting superellipse rings along X.
    stations: list of (x, z_bottom, z_top, half_width), ordered along X.
    """
    bm = bmesh.new()
    rings = []
    for (x, zb, zt, w) in stations:
        zc, hh = (zb + zt) / 2, (zt - zb) / 2
        ring = []
        for i in range(M):
            t = 2 * pi * i / M
            y = w * sgnpow(math.cos(t), 2 / n)
            z = zc + hh * sgnpow(math.sin(t), 2 / n)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(M):
            j = (i + 1) % M
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    bm.faces.new(rings[0])       # end caps keep the mesh watertight
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for m in mats:
        mesh.materials.append(m)
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    for p in mesh.polygons:
        p.use_smooth = True
    return parent(obj)


def bake_modifiers(obj):
    """Apply every modifier on obj (version-independent)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    new_mesh = bpy.data.meshes.new_from_object(ev)
    old = obj.data
    obj.modifiers.clear()
    obj.data = new_mesh
    bpy.data.meshes.remove(old)
    for p in obj.data.polygons:
        p.use_smooth = True


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
paint = make_mat("Torch_Red", (0.55, 0.005, 0.01), metallic=0.45, rough=0.22, coat=1.0)
glass = make_mat("Glass", (0.01, 0.012, 0.015), metallic=0.0, rough=0.04, coat=0.5)
black = make_mat("Black_Plastic", (0.015, 0.015, 0.017), rough=0.45)
carbon = make_mat("Carbon", (0.01, 0.01, 0.012), metallic=0.3, rough=0.25, coat=1.0)
rubber = make_mat("Rubber", (0.02, 0.02, 0.02), rough=0.85)
rim_dark = make_mat("Rim_Dark", (0.03, 0.03, 0.035), metallic=0.9, rough=0.3)
rim_spoke = make_mat("Rim_Spoke", (0.18, 0.18, 0.2), metallic=1.0, rough=0.25)
chrome = make_mat("Exhaust", (0.7, 0.7, 0.72), metallic=1.0, rough=0.2)
tail_mat = make_mat("Taillight", (0.8, 0.0, 0.0), rough=0.2, emit=(1.0, 0.0, 0.0), emit_strength=3.0)
head_mat = make_mat("Headlight", (0.9, 0.9, 1.0), rough=0.1, emit=(0.9, 0.95, 1.0), emit_strength=2.0)

# ----------------------------------------------------------------------------
# Body shell   (x, z_bottom, z_top, half_width)
# ----------------------------------------------------------------------------
BODY = [
    (2.35, 0.28, 0.46, 0.45),   # nose tip
    (2.25, 0.20, 0.55, 0.78),
    (2.05, 0.15, 0.64, 0.92),
    (1.60, 0.14, 0.78, 0.97),
    (1.00, 0.14, 0.86, 0.98),   # hood / front fender
    (0.40, 0.14, 0.90, 0.98),   # doors
    (-0.30, 0.14, 0.96, 1.00),
    (-1.00, 0.14, 1.00, 1.02),  # rear haunches
    (-1.70, 0.16, 1.00, 1.02),
    (-2.15, 0.20, 0.90, 0.92),
    (-2.38, 0.28, 0.78, 0.70),
    (-2.45, 0.35, 0.70, 0.50),  # tail
]
body = loft("Body", BODY, [paint], M=20, n=3.0)

sub = body.modifiers.new("Subsurf", 'SUBSURF')
sub.levels = 3
sub.render_levels = 3

# wheel layout
FRONT_X, REAR_X = 1.45, -1.30
Y_FRONT, Y_REAR = 0.88, 0.89
R_FRONT, R_REAR = 0.34, 0.36
W_FRONT, W_REAR = 0.28, 0.34

# boolean cutters for wheel arches
cutters = []
for sx, x, r in ((1, FRONT_X, R_FRONT), (-1, REAR_X, R_REAR)):
    for sy in (1, -1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=r + 0.05, depth=1.0,
                                            location=(x, sy * 0.8, r), rotation=(pi / 2, 0, 0))
        c = bpy.context.active_object
        c.name = f"ArchCutter_{sx}_{sy}"
        cutters.append(c)
        mod = body.modifiers.new(c.name, 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = c

bake_modifiers(body)
for c in cutters:
    bpy.data.objects.remove(c, do_unlink=True)

# ----------------------------------------------------------------------------
# Cabin / greenhouse (glass with red roof panel)
# ----------------------------------------------------------------------------
CABIN = [
    (1.00, 0.78, 0.84, 0.55),
    (0.60, 0.80, 1.05, 0.80),
    (0.10, 0.82, 1.16, 0.84),
    (-0.40, 0.84, 1.15, 0.84),
    (-0.90, 0.88, 1.06, 0.78),
    (-1.30, 0.92, 1.00, 0.55),
]
cabin = loft("Cabin", CABIN, [glass, paint], M=20, n=2.6)
for p in cabin.data.polygons:                      # red roof where faces point up
    if p.center.z > 1.04 and p.normal.z > 0.75:
        p.material_index = 1
cs = cabin.modifiers.new("Subsurf", 'SUBSURF')
cs.levels = 2
cs.render_levels = 2

# ----------------------------------------------------------------------------
# Wheels
# ----------------------------------------------------------------------------
def make_wheel(tag, x, side, r_tire, width, y_pos):
    y = side * y_pos
    z = r_tire
    r_rim = r_tire * 0.72
    add_cyl(f"{tag}_Tire", r_tire, width, (x, y, z), mat=rubber, verts=64)
    add_cyl(f"{tag}_Rim", r_rim, width * 0.86, (x, y, z), mat=rim_dark)
    y_out = y + side * (width / 2 - 0.05)
    for k in range(5):                              # 5 diametric bars = 10 spokes
        add_box(f"{tag}_Spoke{k}", (x, y_out, z),
                (2 * r_rim * 0.92, 0.03, 0.05), rim_spoke, rot=(0, k * pi / 5, 0))
    add_cyl(f"{tag}_Hub", 0.06, 0.06, (x, y_out, z), mat=rim_spoke, verts=24)


for side in (1, -1):
    s = "R" if side == 1 else "L"
    make_wheel(f"Front{s}", FRONT_X, side, R_FRONT, W_FRONT, Y_FRONT)
    make_wheel(f"Rear{s}", REAR_X, side, R_REAR, W_REAR, Y_REAR)

# ----------------------------------------------------------------------------
# Aero + details
# ----------------------------------------------------------------------------
# front splitter, rear diffuser
add_box("Splitter", (2.22, 0, 0.12), (0.50, 1.50, 0.03), carbon)
add_box("Diffuser", (-2.28, 0, 0.17), (0.40, 1.10, 0.03), carbon)

# side intakes, mirrors, lights
for side in (1, -1):
    add_box(f"SideIntake_{side}", (-0.95, side * 1.00, 0.52), (0.55, 0.04, 0.16), black)
    add_box(f"Mirror_{side}", (0.55, side * 0.93, 0.99), (0.14, 0.10, 0.07), paint)
    add_box(f"Headlight_{side}", (1.98, side * 0.62, 0.62), (0.25, 0.30, 0.035),
            head_mat, rot=(0, radians(14), radians(-side * 12)))
    add_box(f"Taillight_{side}", (-2.36, side * 0.45, 0.66), (0.06, 0.35, 0.05), tail_mat)
    add_cyl(f"Exhaust_{side}", 0.06, 0.22, (-2.36, side * 0.25, 0.30),
            rot=(0, pi / 2, 0), mat=chrome, verts=24)

# hood vent
add_box("HoodVent", (1.45, 0, 0.775), (0.35, 0.40, 0.02), black, rot=(0, radians(4), 0))

# rear wing: blade, end plates, uprights
WING_X, WING_Z = -2.50, 1.30
add_box("Wing_Blade", (WING_X, 0, WING_Z), (0.38, 1.80, 0.03), carbon, rot=(0, radians(-8), 0))
for side in (1, -1):
    add_box(f"Wing_EndPlate_{side}", (WING_X, side * 0.90, WING_Z - 0.02), (0.48, 0.02, 0.20), carbon)
    add_box(f"Wing_Upright_{side}", (WING_X + 0.05, side * 0.50, 1.02), (0.05, 0.04, 0.55), carbon,
            rot=(0, radians(-8), 0))

# ----------------------------------------------------------------------------
# Scene: ground, lights, camera, world
# ----------------------------------------------------------------------------
if RENDER_SCENE:
    asphalt = make_mat("Wet_Asphalt", (0.07, 0.07, 0.075), rough=0.18)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground.data.materials.append(asphalt)

    # sky / world
    world = bpy.data.worlds.new("World") if not scene.world else scene.world
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.58, 1.0)
    bg.inputs["Strength"].default_value = 1.0

    # lights
    bpy.ops.object.light_add(type='SUN', location=(6, -6, 10), rotation=(radians(50), 0, radians(35)))
    sun = bpy.context.active_object
    sun.data.energy = 3.0
    bpy.ops.object.light_add(type='AREA', location=(0, -6, 5))
    area = bpy.context.active_object
    area.data.energy = 600
    area.data.size = 6
    area.rotation_euler = (radians(60), 0, 0)

    # camera aimed at the car (side / slight 3-quarter, front pointing right)
    bpy.ops.object.empty_add(location=(0, 0, 0.6))
    target = bpy.context.active_object
    target.name = "Cam_Target"
    bpy.ops.object.camera_add(location=(3.0, -11.0, 1.1))
    cam = bpy.context.active_object
    cam.data.lens = 85
    track = cam.constraints.new('TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    scene.camera = cam

    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080

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

print("Supercar built: parent object is 'Car_Root' (move/rotate it to place the car).")
