"""
Tensile-membrane car-park shade (cantilevered, single-column, arched ribs)
Blender 3.0+ / 4.x

HOW TO RUN
  Blender -> Scripting workspace -> Text > Open -> this file -> Alt+P.
  Numpad 0 = camera view, F12 = render.

LAYOUT (meters)
  X = along the row of columns,  Y = across (canopy cantilevers toward -Y for row 1),
  Z = up.  Each column carries a big arched tube; fabric is stretched between
  neighbouring arches with a scalloped free edge.  Everything is parented to
  "Shade_Root".

TWEAK the parameters below: BAYS, ROWS, BAY_SPAN, heights, scallop depth...
"""
import math
from math import pi, radians, sin

import bmesh
import bpy
from mathutils import Matrix, Vector

# ----------------------------------------------------------------------------
# Parameters
# ----------------------------------------------------------------------------
BAYS = 6                 # number of fabric bays per row  (columns = BAYS + 1)
ROWS = 2                 # 1 or 2 (second row mirrored across the aisle)
BAY_SPAN = 5.5           # distance between ribs / columns
AISLE = 7.0              # drive aisle width between the two rows (ROWS = 2)

Z_PEAK = 5.0             # height of the arch crest above the column
S_BACK = -1.8            # rib length behind the column (small back overhang)
S_FREE = 8.4             # rib length in front of the column (cantilever)
S_PEAK = -0.4            # position of the crest relative to the column
DROP_FRONT = 1.9         # how far the free end drops below the crest
A_BACK = 0.09            # parabola curvature of the short back end
RIB_R = 0.17             # arch tube radius
COL_R = 0.14             # column radius

SCALLOP = 2.3            # how far the fabric edge is pulled in between ribs
SAG = 0.38               # fabric sag at mid-bay
NU, NV = 16, 28          # fabric mesh resolution per bay

USE_CYCLES = True

A_FRONT = DROP_FRONT / (S_FREE - S_PEAK) ** 2

# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene
root = bpy.data.objects.new("Shade_Root", None)
scene.collection.objects.link(root)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def set_in(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return


def make_mat(name, color, metallic=0.0, rough=0.5, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    set_in(b, ["Base Color"], (*color, 1))
    set_in(b, ["Metallic"], metallic)
    set_in(b, ["Roughness"], rough)
    if emit:
        set_in(b, ["Emission Color", "Emission"], (*emit, 1))
        set_in(b, ["Emission Strength"], emit_strength)
    return m


def adopt(o, mat=None, smooth=True):
    if mat:
        o.data.materials.append(mat)
    if smooth and o.type == 'MESH':
        for p in o.data.polygons:
            p.use_smooth = True
    o.parent = root
    return o


def beam(name, p1, p2, r, mat, segs=20):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(vertices=segs, radius=r, depth=d.length,
                                        location=(p1 + p2) / 2)
    o = bpy.context.active_object
    o.name = name
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return adopt(o, mat)


def box(name, loc, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    return adopt(o, mat, smooth=False)


def tube(name, pts, radii, mat):
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    cd.bevel_depth = 1.0
    cd.bevel_resolution = 6
    cd.fill_mode = 'FULL'
    cd.use_fill_caps = True
    sp = cd.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, pt, r in zip(sp.points, pts, radii):
        p.co = (pt.x, pt.y, pt.z, 1.0)
        p.radius = r
    cd.materials.append(mat)
    o = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(o)
    o.parent = root
    return o


def merged_mesh(name, bm, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    return adopt(o, mat)


def rib_z(s):
    d = s - S_PEAK
    a = A_FRONT if d > 0 else A_BACK
    return Z_PEAK - a * d * d


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
white = make_mat("Steel_White", (0.9, 0.9, 0.9), metallic=0.1, rough=0.32)
fabric = make_mat("Fabric", (0.80, 0.75, 0.62), rough=0.8, emit=(0.8, 0.72, 0.55), emit_strength=0.12)
concrete = make_mat("Concrete", (0.55, 0.55, 0.52), rough=0.9)
asphalt = make_mat("Asphalt", (0.045, 0.045, 0.05), rough=0.85)
paint = make_mat("Line_Paint", (0.9, 0.9, 0.9), rough=0.6)
grass = make_mat("Grass", (0.10, 0.20, 0.04), rough=0.95)
cone_m = make_mat("Cone", (1.0, 0.25, 0.02), rough=0.5)
bolt_m = make_mat("Bolt", (0.8, 0.8, 0.82), metallic=1.0, rough=0.25)

bolts = []     # (position, radius) merged at the end into one object


# ----------------------------------------------------------------------------
# One row of ribs + columns + fabric
# ----------------------------------------------------------------------------
def build_row(tag, y_col, dirn):
    """dirn = +1: canopy extends toward -Y,  dirn = -1: toward +Y."""
    def Y(s):
        return y_col - dirn * s

    n_ribs = BAYS + 1
    for i in range(n_ribs):
        x = i * BAY_SPAN

        # arched tube
        N = 44
        pts, radii = [], []
        for k in range(N + 1):
            t = k / N
            s = S_BACK + (S_FREE - S_BACK) * t
            pts.append(Vector((x, Y(s), rib_z(s))))
            radii.append(RIB_R * (1.0 - 0.18 * t))
        tube(f"{tag}_Rib_{i}", pts, radii, white)

        # row of bolts along the crest of the rib
        s = S_BACK + 0.3
        while s < S_FREE - 0.1:
            bolts.append((Vector((x, Y(s), rib_z(s) + RIB_R * 0.95)), 0.032))
            s += 0.55

        # column, base plate, concrete footing
        z_top = rib_z(0.0) - RIB_R
        beam(f"{tag}_Column_{i}", (x, Y(0), 0.45), (x, Y(0), z_top), COL_R, white, 32)
        box(f"{tag}_Bracket_{i}", (x, Y(0), z_top - 0.12), (0.36, 0.40, 0.34), white)
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.52, depth=0.42, location=(x, Y(0), 0.21))
        ft = bpy.context.active_object
        ft.name = f"{tag}_Footing_{i}"
        adopt(ft, concrete)
        box(f"{tag}_BasePlate_{i}", (x, Y(0), 0.44), (0.56, 0.56, 0.04), white)
        for bx in (-0.2, 0.2):
            for by in (-0.2, 0.2):
                bolts.append((Vector((x + bx, Y(0) + by, 0.475)), 0.032))
        # gusset ring where the column meets the plate
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.24, radius2=COL_R, depth=0.22,
                                        location=(x, Y(0), 0.57))
        g = bpy.context.active_object
        g.name = f"{tag}_Gusset_{i}"
        adopt(g, white)

        # diagonal strut from column up to the arch
        p_col = Vector((x, Y(0.0), 3.35))
        p_rib = Vector((x, Y(4.6), rib_z(4.6) - RIB_R * 0.9))
        beam(f"{tag}_Strut_{i}", p_col, p_rib, 0.065, white, 16)
        for pp in (p_col, p_rib):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.1, location=pp)
            sp = bpy.context.active_object
            sp.name = f"{tag}_Pivot"
            adopt(sp, white)

    # ---- fabric membrane across all bays (single continuous grid) -----------
    bm = bmesh.new()
    total = BAYS * NU
    grid = []
    for k in range(total + 1):
        x = k * BAY_SPAN / NU
        u = (k % NU) / NU
        su = sin(pi * u)
        s_free = S_FREE - SCALLOP * su ** 0.7
        row = []
        for j in range(NV + 1):
            v = j / NV
            s = S_BACK + (s_free - S_BACK) * v
            z = rib_z(s) + RIB_R * 0.75 - SAG * su * (0.6 + 0.4 * v)
            row.append(bm.verts.new((x, Y(s), z)))
        grid.append(row)
    for k in range(total):
        for j in range(NV):
            bm.faces.new((grid[k][j], grid[k + 1][j], grid[k + 1][j + 1], grid[k][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    edge_pts = [grid[k][NV].co.copy() for k in range(total + 1)]
    fab = merged_mesh(f"{tag}_Fabric", bm, fabric)
    sol = fab.modifiers.new("Solidify", 'SOLIDIFY')
    sol.thickness = 0.012
    sol.offset = 0.0

    # edge cable along the scalloped free edge
    tube(f"{tag}_EdgeCable", edge_pts, [0.022] * len(edge_pts), white)

    # kerb behind the columns
    row_len = BAYS * BAY_SPAN
    box(f"{tag}_Kerb", (row_len / 2, Y(-1.15), 0.08), (row_len + 14, 0.3, 0.16), concrete)

    # parking bay lines (painted from the kerb out under the canopy)
    lm = bmesh.new()
    n_lines = BAYS * 2 + 1
    for k in range(n_lines):
        x = k * BAY_SPAN / 2
        s_mid = 2.9
        M = (Matrix.Translation((x, Y(s_mid), 0.012))
             @ Matrix.Diagonal(Vector((0.1, 5.2, 0.004, 1.0))))
        bmesh.ops.create_cube(lm, size=1.0, matrix=M)
    merged_mesh(f"{tag}_BayLines", lm, paint)


# ----------------------------------------------------------------------------
# Build rows
# ----------------------------------------------------------------------------
Y_COL_1 = 0.0
build_row("RowA", Y_COL_1, +1)
if ROWS == 2:
    Y_COL_2 = -(2 * S_FREE + AISLE)
    build_row("RowB", Y_COL_2, -1)
else:
    Y_COL_2 = Y_COL_1 - S_FREE

# merged bolts (rib crests + base plates)
bm = bmesh.new()
for pos, r in bolts:
    try:
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r, matrix=Matrix.Translation(pos))
    except TypeError:
        bmesh.ops.create_icosphere(bm, subdivisions=1, diameter=r, matrix=Matrix.Translation(pos))
merged_mesh("Bolts", bm, bolt_m)

# ----------------------------------------------------------------------------
# Ground: grass, asphalt, cones
# ----------------------------------------------------------------------------
row_len = BAYS * BAY_SPAN
x0, x1 = -12.0, row_len + 14.0
y_hi, y_lo = Y_COL_1 + 1.0, Y_COL_2 - (1.0 if ROWS == 2 else S_FREE)
bpy.ops.mesh.primitive_plane_add(size=300, location=(row_len / 2, -10, -0.02))
gr = bpy.context.active_object
gr.name = "Grass"
adopt(gr, grass, smooth=False)
box("Asphalt", ((x0 + x1) / 2, (y_hi + y_lo) / 2, 0.005), (x1 - x0, y_hi - y_lo, 0.02), asphalt)

for i, (cx, cy) in enumerate(((4.0, -3.5), (9.0, -6.0), (-1.5, -9.0))):
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.17, radius2=0.03, depth=0.55,
                                    location=(cx, cy, 0.3))
    c = bpy.context.active_object
    c.name = f"Cone_{i}"
    adopt(c, cone_m)

# ----------------------------------------------------------------------------
# Sky, lights, camera
# ----------------------------------------------------------------------------
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.72, 0.78, 0.88, 1)     # soft overcast sky
bg.inputs["Strength"].default_value = 1.3

bpy.ops.object.light_add(type='SUN', location=(-10, -15, 25), rotation=(radians(50), 0, radians(-25)))
sun = bpy.context.active_object
sun.data.energy = 2.5
sun.data.angle = radians(8)

bpy.ops.object.empty_add(location=(28, -2.5, 3.2))
tgt = bpy.context.active_object
tgt.name = "Cam_Target"
bpy.ops.object.camera_add(location=(-3.5, -4.6, 1.7))
cam = bpy.context.active_object
cam.data.lens = 22
tc = cam.constraints.new('TRACK_TO')
tc.target = tgt
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'
scene.camera = cam
scene.render.resolution_x = 1600
scene.render.resolution_y = 1066

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

print("Parking shade built. Parent object: 'Shade_Root'.")
