"""
Procedural broad-crowned oak tree for Blender 3.x / 4.x
Matches the look of the reference photo: short trunk, wide spreading limbs,
dense rounded green crown, blue sky.

HOW TO RUN
  1. Blender -> Scripting workspace -> Text > Open -> choose this file.
  2. Press Alt+P (Run Script).
  3. Numpad 0 = camera view, F12 = render.

TWEAK
  SEED          -> different random tree each value
  MAX_DEPTH     -> branching levels (more = denser, slower)
  LEAF_*        -> size / amount of leaf blobs
"""
import math
import random
from math import pi, radians

import bmesh
import bpy
from mathutils import Quaternion, Vector

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
SEED = 7
MAX_DEPTH = 5            # recursion levels of branching
TRUNK_HEIGHT = 3.2
TRUNK_RADIUS = 0.30
LIMB_COUNT = 5           # main limbs leaving the trunk
LENGTH_FALLOFF = 0.74    # branch length multiplier per level
CHILDREN = (2, 4)        # min / max child branches
LEAF_BLOBS_PER_TIP = (3, 5)
LEAF_SIZE = (0.9, 1.5)   # blob radius range (meters)
USE_CYCLES = True
ADD_SCENE = True         # ground, sky, sun, camera

random.seed(SEED)

# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
def set_in(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return


bark_mat = bpy.data.materials.new("Bark")
bark_mat.use_nodes = True
b = bark_mat.node_tree.nodes["Principled BSDF"]
set_in(b, ["Base Color"], (0.075, 0.05, 0.035, 1))
set_in(b, ["Roughness"], 0.92)

leaf_mat = bpy.data.materials.new("Leaves")
leaf_mat.use_nodes = True
nt = leaf_mat.node_tree
lb = nt.nodes["Principled BSDF"]
set_in(lb, ["Roughness"], 0.6)
set_in(lb, ["Subsurface Weight", "Subsurface"], 0.15)
vcol = nt.nodes.new("ShaderNodeVertexColor")
vcol.layer_name = "Col"
nt.links.new(vcol.outputs["Color"], lb.inputs["Base Color"])

# ----------------------------------------------------------------------------
# Branches (one curve object, many splines, tapered by point radius)
# ----------------------------------------------------------------------------
curve = bpy.data.curves.new("TreeBranches", 'CURVE')
curve.dimensions = '3D'
curve.bevel_depth = 1.0          # real thickness comes from per-point radius
curve.bevel_resolution = 3
curve.fill_mode = 'FULL'
curve.use_fill_caps = True

leaf_centers = []                # (center, base_radius)


def add_spline(points, radii):
    sp = curve.splines.new('POLY')
    sp.points.add(len(points) - 1)
    for p, pt, r in zip(sp.points, points, radii):
        p.co = (pt.x, pt.y, pt.z, 1.0)
        p.radius = r


def rand_unit():
    v = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)))
    return v.normalized() if v.length > 1e-4 else Vector((0, 0, 1))


def grow(start, direction, length, radius, depth):
    segs = 4
    cur = start.copy()
    d = direction.copy()
    pts, rads = [cur.copy()], [radius]
    end_radius = radius * 0.62
    for i in range(1, segs + 1):
        d = (d + rand_unit() * 0.18).normalized()
        if depth >= 3:                       # twigs droop a little
            d.z -= 0.04
            d.normalize()
        cur = cur + d * (length / segs)
        pts.append(cur.copy())
        rads.append(radius + (end_radius - radius) * i / segs)
    add_spline(pts, rads)

    # leaf blobs on last two levels (fuller crown)
    if depth >= MAX_DEPTH - 1:
        n = random.randint(*LEAF_BLOBS_PER_TIP) if depth == MAX_DEPTH else 1
        for _ in range(n):
            off = rand_unit() * length * 0.9
            off.z = abs(off.z) * 0.6 + off.z * 0.4
            leaf_centers.append(cur + off)
        if depth == MAX_DEPTH:
            return

    if depth == 0:
        children = []
        base_az = random.uniform(0, 2 * pi)
        for k in range(LIMB_COUNT):
            az = base_az + 2 * pi * k / LIMB_COUNT + random.uniform(-0.25, 0.25)
            el = radians(random.uniform(38, 62))
            children.append(Vector((math.sin(el) * math.cos(az),
                                    math.sin(el) * math.sin(az),
                                    math.cos(el))))
    else:
        children = []
        for _ in range(random.randint(*CHILDREN)):
            axis = d.cross(rand_unit())
            if axis.length < 1e-4:
                axis = Vector((1, 0, 0))
            axis.normalize()
            q = Quaternion(axis, radians(random.uniform(22, 52)))
            nd = q @ d
            nd.z += 0.12                      # slight upward tropism
            children.append(nd.normalized())

    for cd in children:
        clen = length * LENGTH_FALLOFF * random.uniform(0.85, 1.15)
        if depth == 0:
            clen = 3.2 * random.uniform(0.9, 1.15)
        grow(cur, cd, clen, end_radius * 0.82, depth + 1)


grow(Vector((0, 0, 0)), Vector((0, 0, 1)), TRUNK_HEIGHT, TRUNK_RADIUS, 0)

# root flare
flare = curve.splines.new('POLY')
flare.points.add(1)
flare.points[0].co = (0, 0, -0.2, 1)
flare.points[0].radius = TRUNK_RADIUS * 1.55
flare.points[1].co = (0, 0, 0.9, 1)
flare.points[1].radius = TRUNK_RADIUS * 1.05

branches = bpy.data.objects.new("Tree_Branches", curve)
scene.collection.objects.link(branches)
curve.materials.append(bark_mat)

# ----------------------------------------------------------------------------
# Leaves: many lumpy blobs merged into a single mesh, random green per blob
# ----------------------------------------------------------------------------
bm = bmesh.new()
vert_color = {}
for c in leaf_centers:
    r = random.uniform(*LEAF_SIZE)
    try:
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    except TypeError:
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, diameter=1.0)
    t = random.random()
    col = (0.03 + 0.20 * t, 0.12 + 0.32 * t, 0.015 + 0.04 * t, 1.0)
    if random.random() < 0.08:                # a few yellow-green highlights
        col = (0.28, 0.42, 0.04, 1.0)
    for v in res["verts"]:
        v.co = c + v.co * r * random.uniform(0.8, 1.2)
        v.co.z = c.z + (v.co.z - c.z) * 0.85  # slightly flattened blobs
        vert_color[v] = col

bm.verts.index_update()
colors = [None] * len(bm.verts)
for v, col in vert_color.items():
    colors[v.index] = col

mesh = bpy.data.meshes.new("Tree_Leaves")
bm.to_mesh(mesh)
bm.free()

# vertex colours (new and old API)
try:
    attr = mesh.color_attributes.new("Col", 'FLOAT_COLOR', 'CORNER')
    for loop in mesh.loops:
        attr.data[loop.index].color = colors[loop.vertex_index]
except Exception:
    vc = mesh.vertex_colors.new(name="Col")
    for loop in mesh.loops:
        vc.data[loop.index].color = colors[loop.vertex_index]

mesh.materials.append(leaf_mat)
for p in mesh.polygons:
    p.use_smooth = True

leaves = bpy.data.objects.new("Tree_Leaves", mesh)
scene.collection.objects.link(leaves)

# noisy displacement -> leafy, broken-up silhouette
tex = bpy.data.textures.new("LeafNoise", 'CLOUDS')
tex.noise_scale = 0.35
tex.noise_depth = 2
disp = leaves.modifiers.new("Displace", 'DISPLACE')
disp.texture = tex
disp.strength = 0.45
disp.mid_level = 0.5

# ----------------------------------------------------------------------------
# Scene: ground, sky, sun, camera
# ----------------------------------------------------------------------------
if ADD_SCENE:
    grass = bpy.data.materials.new("Grass")
    grass.use_nodes = True
    gb = grass.node_tree.nodes["Principled BSDF"]
    set_in(gb, ["Base Color"], (0.08, 0.2, 0.04, 1))
    set_in(gb, ["Roughness"], 0.9)
    bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground.data.materials.append(grass)

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.12, 0.32, 0.85, 1)   # blue sky
    bg.inputs["Strength"].default_value = 1.3

    bpy.ops.object.light_add(type='SUN', location=(10, -10, 20),
                             rotation=(radians(45), 0, radians(35)))
    sun = bpy.context.active_object
    sun.data.energy = 4.0
    sun.data.angle = radians(2)

    bpy.ops.object.empty_add(location=(0, 0, 7.5))
    target = bpy.context.active_object
    target.name = "Cam_Target"
    bpy.ops.object.camera_add(location=(0, -26, 3.0))
    cam = bpy.context.active_object
    cam.data.lens = 35
    tc = cam.constraints.new('TRACK_TO')
    tc.target = target
    tc.track_axis = 'TRACK_NEGATIVE_Z'
    tc.up_axis = 'UP_Y'
    scene.camera = cam

    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1080

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

print(f"Tree built: {len(curve.splines)} branches, {len(leaf_centers)} leaf blobs.")
