"""
integrate_new_campus_assets.py
------------------------------
Integrates new procedural assets into the IMRD Campus Blender scene with
rich, accurate, and vivid PBR colors and viewport diffuse settings:
1. Procedural Oak Trees (realistic broad-crowned trees with lush green foliage and bark brown trunks).
2. Procedural Supercars (Corvette Z06 in Torch Red, Velocity Yellow, Ceramic White, Elkhart Blue with carbon aero and chrome exhausts).
3. Tensile Parking Shades (architectural white steel tubes, off-white translucent membrane fabric, concrete footings).
4. Mountain Bikes (vibrant frame colors: Orange, Cyan, Crimson, Stealth Black, Lime Green, Sunburst Gold).
5. Seminar Hall (velvet crimson audience seats, two-tone acoustic wood paneling, hardwood stage, glowing screen, red banners).
6. Academic Library (golden honey oak bookshelves, multi-colored book bindings, beech study tables, navy cushions, digital kiosk).
7. Badminton Court (BWF tournament emerald green PU court, parquet wood surround, crisp white lines, yellow posts, white net).
8. Park Benches (Victorian black cast iron frames, warm mahogany wood slats).
"""

import math
import random
from math import pi, radians
import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

# ----------------------------------------------------------------------------
# General Helpers
# ----------------------------------------------------------------------------
def get_or_create_col(name, parent_col=None):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        if parent_col:
            parent_col.children.link(col)
        else:
            bpy.context.scene.collection.children.link(col)
    return col


def link_only_to(obj, col):
    if obj.name not in col.objects:
        col.objects.link(obj)
    for c in list(obj.users_collection):
        if c != col:
            c.objects.unlink(obj)
    return obj


def set_in(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return


def make_pbr_mat(name, color, metallic=0.0, rough=0.5, coat=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.get(name)
    if not m:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*color[:3], 1.0)
    m.roughness = rough
    m.metallic = metallic

    b = m.node_tree.nodes.get("Principled BSDF")
    if not b:
        b = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    set_in(b, ["Base Color"], (*color[:3], 1.0))
    set_in(b, ["Metallic"], metallic)
    set_in(b, ["Roughness"], rough)
    set_in(b, ["Coat Weight", "Clearcoat"], coat)
    set_in(b, ["Coat Roughness", "Clearcoat Roughness"], 0.03)
    if emit:
        set_in(b, ["Emission Color", "Emission"], (*emit[:3], 1.0))
        set_in(b, ["Emission Strength"], emit_strength)
    return m


def sgnpow(v, p):
    return math.copysign(abs(v) ** p, v)


# ----------------------------------------------------------------------------
# 1. CLEANUP PHASE
# ----------------------------------------------------------------------------
def cleanup_old_assets():
    print("--- Cleaning old junk assets & colored trees ---")
    # Remove junk collections
    for c in list(bpy.data.collections):
        if any(k in c.name.lower() for k in ["imported_assets", "cut out", "daun", "panel gap", "rumput"]):
            for obj in list(c.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(c)

    # Remove any existing procedural assets from previous runs to ensure idempotency
    prefixes_to_clean = [
        "Oak_Tree", "Corvette_Z06", "Car_Parking_Shade", "Bike_Parking_Shade",
        "Mountain_Bike", "SH_", "Lib_", "BC_", "Park_Bench",
        "ShadeTree_", "Car_0_", "Car_1_", "Car_2_", "Car_5_", "Bike_3_", "Bike_4_",
        "Student_Bike_", "Bike_Canopy_", "Bike_Rack_Stand_", "Bike_Station_Pad"
    ]
    for o in list(bpy.data.objects):
        if any(o.name.startswith(p) for p in prefixes_to_clean):
            bpy.data.objects.remove(o, do_unlink=True)

    # Clean orphaned datablocks
    for block in [bpy.data.meshes, bpy.data.materials, bpy.data.curves]:
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    print("Cleanup complete.")


# ----------------------------------------------------------------------------
# 2. OAK TREE BUILDER
# ----------------------------------------------------------------------------
def build_oak_tree(target_col, location, scale=1.0, seed=7, name_prefix="Oak_Tree"):
    random.seed(seed)
    MAX_DEPTH = 4
    TRUNK_HEIGHT = 3.2 * scale
    TRUNK_RADIUS = 0.32 * scale
    LIMB_COUNT = 5
    LENGTH_FALLOFF = 0.74
    CHILDREN = (2, 3)
    LEAF_BLOBS_PER_TIP = (3, 4)
    LEAF_SIZE = (0.9 * scale, 1.4 * scale)

    # Rich bark material (warm organic woody brown)
    bark_mat = make_pbr_mat("Bark_Oak", (0.18, 0.11, 0.06), rough=0.92)

    # Lush forest canopy green leaves with vertex color modulation & fallback
    leaf_mat = bpy.data.materials.get("Leaves_Oak")
    if not leaf_mat:
        leaf_mat = bpy.data.materials.new("Leaves_Oak")
    leaf_mat.use_nodes = True
    leaf_mat.diffuse_color = (0.12, 0.40, 0.08, 1.0)
    leaf_mat.roughness = 0.6
    nt = leaf_mat.node_tree
    lb = nt.nodes.get("Principled BSDF")
    if not lb:
        lb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    set_in(lb, ["Base Color"], (0.12, 0.38, 0.08, 1.0))
    set_in(lb, ["Roughness"], 0.6)
    set_in(lb, ["Subsurface Weight", "Subsurface"], 0.15)
    attr_node = nt.nodes.get("Attribute_Col")
    if not attr_node:
        attr_node = nt.nodes.new("ShaderNodeAttribute")
        attr_node.name = "Attribute_Col"
        attr_node.attribute_name = "Col"
        nt.links.new(attr_node.outputs["Color"], lb.inputs["Base Color"])

    # Curve Branches
    curve = bpy.data.curves.new(f"{name_prefix}_Branches_Curve", 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = 1.0
    curve.bevel_resolution = 3
    curve.fill_mode = 'FULL'
    curve.use_fill_caps = True
    leaf_centers = []

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
            if depth >= 2:
                d.z -= 0.04
                d.normalize()
            cur = cur + d * (length / segs)
            pts.append(cur.copy())
            rads.append(radius + (end_radius - radius) * i / segs)
        add_spline(pts, rads)

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
                nd.z += 0.12
                children.append(nd.normalized())

        for cd in children:
            clen = length * LENGTH_FALLOFF * random.uniform(0.85, 1.15)
            if depth == 0:
                clen = 3.2 * scale * random.uniform(0.9, 1.15)
            grow(cur, cd, clen, end_radius * 0.82, depth + 1)

    grow(Vector((0, 0, 0)), Vector((0, 0, 1)), TRUNK_HEIGHT, TRUNK_RADIUS, 0)

    # Root flare
    flare = curve.splines.new('POLY')
    flare.points.add(1)
    flare.points[0].co = (0, 0, -0.2 * scale, 1)
    flare.points[0].radius = TRUNK_RADIUS * 1.55
    flare.points[1].co = (0, 0, 0.9 * scale, 1)
    flare.points[1].radius = TRUNK_RADIUS * 1.05

    branches = bpy.data.objects.new(f"{name_prefix}_Branches", curve)
    link_only_to(branches, target_col)
    curve.materials.append(bark_mat)

    # Leaf Mesh with color layer
    bm = bmesh.new()
    color_lay = bm.loops.layers.color.new("Col")
    for c in leaf_centers:
        r = random.uniform(*LEAF_SIZE)
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        t = random.random()
        col = (0.04 + 0.18 * t, 0.22 + 0.36 * t, 0.02 + 0.04 * t, 1.0)
        if random.random() < 0.10:
            col = (0.32, 0.48, 0.05, 1.0)
        for v in res["verts"]:
            v.co = c + v.co * r * random.uniform(0.8, 1.2)
            v.co.z = c.z + (v.co.z - c.z) * 0.85
            for loop in v.link_loops:
                loop[color_lay] = col

    mesh = bpy.data.meshes.new(f"{name_prefix}_Leaves_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    mesh.materials.append(leaf_mat)
    for p in mesh.polygons:
        p.use_smooth = True

    leaves = bpy.data.objects.new(f"{name_prefix}_Leaves", mesh)
    link_only_to(leaves, target_col)

    # Broken silhouette displacement
    tex = bpy.data.textures.get("LeafNoise")
    if not tex:
        tex = bpy.data.textures.new("LeafNoise", 'CLOUDS')
        tex.noise_scale = 0.35
        tex.noise_depth = 2
    disp = leaves.modifiers.new("Displace", 'DISPLACE')
    disp.texture = tex
    disp.strength = 0.40 * scale
    disp.mid_level = 0.5

    # Group under root empty
    root = bpy.data.objects.new(name_prefix, None)
    link_only_to(root, target_col)
    root.location = location
    branches.parent = root
    leaves.parent = root
    return root


# ----------------------------------------------------------------------------
# 3. CORVETTE Z06 SUPERCAR BUILDER
# ----------------------------------------------------------------------------
def build_corvette_z06(target_col, location, rot_z=0.0, paint_color=(0.82, 0.02, 0.03), name="Corvette_Z06"):
    root = bpy.data.objects.new(name, None)
    link_only_to(root, target_col)

    paint_mat = make_pbr_mat(f"{name}_Paint", paint_color, metallic=0.55, rough=0.18, coat=1.0)
    glass_mat = make_pbr_mat("Car_Glass", (0.04, 0.06, 0.08), metallic=0.0, rough=0.05, coat=0.6)
    black_mat = make_pbr_mat("Car_Black", (0.02, 0.02, 0.022), rough=0.45)
    carbon_mat = make_pbr_mat("Car_Carbon", (0.02, 0.02, 0.025), metallic=0.3, rough=0.25, coat=1.0)
    rubber_mat = make_pbr_mat("Car_Rubber", (0.025, 0.025, 0.025), rough=0.85)
    rim_dark = make_pbr_mat("Car_RimDark", (0.07, 0.07, 0.08), metallic=0.9, rough=0.3)
    rim_spoke = make_pbr_mat("Car_RimSpoke", (0.85, 0.85, 0.88), metallic=1.0, rough=0.20)
    chrome_mat = make_pbr_mat("Car_Chrome", (0.88, 0.88, 0.90), metallic=1.0, rough=0.15)
    tail_mat = make_pbr_mat("Car_Taillight", (0.95, 0.02, 0.02), rough=0.2, emit=(1.0, 0.0, 0.0), emit_strength=3.0)
    head_mat = make_pbr_mat("Car_Headlight", (0.95, 0.98, 1.0), rough=0.1, emit=(0.95, 0.98, 1.0), emit_strength=3.0)

    def parent_obj(o):
        o.parent = root
        return o

    def add_cyl(c_name, r, depth, loc, rot=(pi / 2, 0, 0), mat=None, verts=32):
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
        o = bpy.context.active_object
        o.name = f"{name}_{c_name}"
        bpy.ops.object.shade_smooth()
        if mat:
            o.data.materials.append(mat)
        link_only_to(o, target_col)
        return parent_obj(o)

    def add_box(b_name, loc, size, mat, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
        o = bpy.context.active_object
        o.name = f"{name}_{b_name}"
        o.scale = size
        if mat:
            o.data.materials.append(mat)
        link_only_to(o, target_col)
        return parent_obj(o)

    def loft(l_name, stations, mats, M=16, n=2.8):
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
        bm.faces.new(rings[0])
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(f"{name}_{l_name}_Mesh")
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(m)
        o = bpy.data.objects.new(f"{name}_{l_name}", me)
        link_only_to(o, target_col)
        for p in me.polygons:
            p.use_smooth = True
        return parent_obj(o)

    # Body stations
    BODY = [
        (2.35, 0.28, 0.46, 0.45),
        (2.25, 0.20, 0.55, 0.78),
        (2.05, 0.15, 0.64, 0.92),
        (1.60, 0.14, 0.78, 0.97),
        (1.00, 0.14, 0.86, 0.98),
        (0.40, 0.14, 0.90, 0.98),
        (-0.30, 0.14, 0.96, 1.00),
        (-1.00, 0.14, 1.00, 1.02),
        (-1.70, 0.16, 1.00, 1.02),
        (-2.15, 0.20, 0.90, 0.92),
        (-2.38, 0.28, 0.78, 0.70),
        (-2.45, 0.35, 0.70, 0.50),
    ]
    body = loft("Body", BODY, [paint_mat], M=16, n=3.0)

    # Cabin stations
    CABIN = [
        (1.00, 0.78, 0.84, 0.55),
        (0.60, 0.80, 1.05, 0.80),
        (0.10, 0.82, 1.16, 0.84),
        (-0.40, 0.84, 1.15, 0.84),
        (-0.90, 0.88, 1.06, 0.78),
        (-1.30, 0.92, 1.00, 0.55),
    ]
    cabin = loft("Cabin", CABIN, [glass_mat, paint_mat], M=16, n=2.6)
    for p in cabin.data.polygons:
        if p.center.z > 1.04 and p.normal.z > 0.75:
            p.material_index = 1

    # Wheels
    FRONT_X, REAR_X = 1.45, -1.30
    Y_FRONT, Y_REAR = 0.88, 0.89
    R_FRONT, R_REAR = 0.34, 0.36
    W_FRONT, W_REAR = 0.28, 0.34

    def make_wheel(tag, x, side, r_tire, width, y_pos):
        y = side * y_pos
        z = r_tire
        r_rim = r_tire * 0.72
        add_cyl(f"{tag}_Tire", r_tire, width, (x, y, z), mat=rubber_mat, verts=32)
        add_cyl(f"{tag}_Rim", r_rim, width * 0.86, (x, y, z), mat=rim_dark, verts=24)
        y_out = y + side * (width / 2 - 0.05)
        for k in range(5):
            add_box(f"{tag}_Spoke{k}", (x, y_out, z), (2 * r_rim * 0.92, 0.03, 0.05), rim_spoke, rot=(0, k * pi / 5, 0))
        add_cyl(f"{tag}_Hub", 0.06, 0.06, (x, y_out, z), mat=rim_spoke, verts=16)

    for side in (1, -1):
        s = "R" if side == 1 else "L"
        make_wheel(f"Front{s}", FRONT_X, side, R_FRONT, W_FRONT, Y_FRONT)
        make_wheel(f"Rear{s}", REAR_X, side, R_REAR, W_REAR, Y_REAR)

    # Aero & Details
    add_box("Splitter", (2.22, 0, 0.12), (0.50, 1.50, 0.03), carbon_mat)
    add_box("Diffuser", (-2.28, 0, 0.17), (0.40, 1.10, 0.03), carbon_mat)
    for side in (1, -1):
        add_box(f"SideIntake_{side}", (-0.95, side * 1.00, 0.52), (0.55, 0.04, 0.16), black_mat)
        add_box(f"Mirror_{side}", (0.55, side * 0.93, 0.99), (0.14, 0.10, 0.07), paint_mat)
        add_box(f"Headlight_{side}", (1.98, side * 0.62, 0.62), (0.25, 0.30, 0.035), head_mat, rot=(0, radians(14), radians(-side * 12)))
        add_box(f"Taillight_{side}", (-2.36, side * 0.45, 0.66), (0.06, 0.35, 0.05), tail_mat)
        add_cyl(f"Exhaust_{side}", 0.06, 0.22, (-2.36, side * 0.25, 0.30), rot=(0, pi / 2, 0), mat=chrome_mat, verts=16)

    add_box("HoodVent", (1.45, 0, 0.775), (0.35, 0.40, 0.02), black_mat, rot=(0, radians(4), 0))
    WING_X, WING_Z = -2.50, 1.30
    add_box("Wing_Blade", (WING_X, 0, WING_Z), (0.38, 1.80, 0.03), carbon_mat, rot=(0, radians(-8), 0))
    for side in (1, -1):
        add_box(f"Wing_EndPlate_{side}", (WING_X, side * 0.90, WING_Z - 0.02), (0.48, 0.02, 0.20), carbon_mat)
        add_box(f"Wing_Upright_{side}", (WING_X + 0.05, side * 0.50, 1.02), (0.05, 0.04, 0.55), carbon_mat, rot=(0, radians(-8), 0))

    # Set root transform
    root.location = location
    root.rotation_euler = (0, 0, rot_z)
    return root


# ----------------------------------------------------------------------------
# 4. TENSILE PARKING SHADE BUILDER
# ----------------------------------------------------------------------------
def build_parking_shade(target_col, location, rot_z=0.0, bays=4, bay_span=4.5, name="Parking_Shade"):
    root = bpy.data.objects.new(name, None)
    link_only_to(root, target_col)

    white_mat = make_pbr_mat("Steel_White", (0.92, 0.92, 0.94), metallic=0.15, rough=0.30)
    fabric_mat = make_pbr_mat("Fabric_Canopy", (0.92, 0.89, 0.82), rough=0.75, emit=(0.85, 0.80, 0.65), emit_strength=0.12)
    conc_mat = make_pbr_mat("Concrete_Base", (0.58, 0.58, 0.55), rough=0.90)

    Z_PEAK = 4.2
    S_BACK = -1.5
    S_FREE = 6.8
    S_PEAK = -0.3
    DROP_FRONT = 1.6
    A_BACK = 0.09
    RIB_R = 0.14
    COL_R = 0.12
    A_FRONT = DROP_FRONT / (S_FREE - S_PEAK) ** 2

    def rib_z(s):
        d = s - S_PEAK
        a = A_FRONT if d > 0 else A_BACK
        return Z_PEAK - a * d * d

    def adopt(o, mat=None):
        if mat:
            o.data.materials.append(mat)
        o.parent = root
        return o

    # Ribs & Columns
    for i in range(bays + 1):
        x = i * bay_span
        cd = bpy.data.curves.new(f"{name}_Rib_{i}_Curve", 'CURVE')
        cd.dimensions = '3D'
        cd.bevel_depth = 1.0
        cd.bevel_resolution = 4
        cd.fill_mode = 'FULL'
        cd.use_fill_caps = True
        sp = cd.splines.new('POLY')
        N = 24
        sp.points.add(N)
        for k in range(N + 1):
            t = k / N
            s = S_BACK + (S_FREE - S_BACK) * t
            sp.points[k].co = (x, -s, rib_z(s), 1.0)
            sp.points[k].radius = RIB_R * (1.0 - 0.15 * t)
        cd.materials.append(white_mat)
        rib_obj = bpy.data.objects.new(f"{name}_Rib_{i}", cd)
        link_only_to(rib_obj, target_col)
        adopt(rib_obj)

        # Column
        z_top = rib_z(0.0) - RIB_R
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=COL_R, depth=z_top - 0.2, location=(x, 0, (0.2 + z_top) / 2))
        col_obj = bpy.context.active_object
        col_obj.name = f"{name}_Col_{i}"
        link_only_to(col_obj, target_col)
        adopt(col_obj, white_mat)

        # Concrete footing
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.45, depth=0.4, location=(x, 0, 0.2))
        ft_obj = bpy.context.active_object
        ft_obj.name = f"{name}_Footing_{i}"
        link_only_to(ft_obj, target_col)
        adopt(ft_obj, conc_mat)

    # Membrane mesh per bay
    NU, NV = 8, 16
    for b in range(bays):
        x0, x1 = b * bay_span, (b + 1) * bay_span
        bm = bmesh.new()
        grid = []
        for iv in range(NV + 1):
            tv = iv / NV
            s = S_BACK + (S_FREE - S_BACK) * tv
            z_rib = rib_z(s)
            edge_sag = 0.35 * math.sin(tv * pi)
            row = []
            for iu in range(NU + 1):
                tu = iu / NU
                x = x0 + (x1 - x0) * tu
                arch = math.sin(tu * pi)
                z = z_rib - edge_sag * arch
                y = -s + (1.2 * arch * (1.0 if tv > 0.5 else -0.3))
                row.append(bm.verts.new((x, y, z)))
            grid.append(row)

        for iv in range(NV):
            for iu in range(NU):
                bm.faces.new((grid[iv][iu], grid[iv][iu + 1], grid[iv + 1][iu + 1], grid[iv + 1][iu]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(f"{name}_Fabric_{b}_Mesh")
        bm.to_mesh(me)
        bm.free()
        fab_obj = bpy.data.objects.new(f"{name}_Fabric_{b}", me)
        link_only_to(fab_obj, target_col)
        for p in me.polygons:
            p.use_smooth = True
        adopt(fab_obj, fabric_mat)

    root.location = location
    root.rotation_euler = (0, 0, rot_z)
    return root


# ----------------------------------------------------------------------------
# 5. MOUNTAIN BIKE BUILDER
# ----------------------------------------------------------------------------
def build_mountain_bike(target_col, location, rot_z=0.0, frame_color=(1.0, 0.32, 0.02), name="Mountain_Bike"):
    root = bpy.data.objects.new(name, None)
    link_only_to(root, target_col)

    frame_mat = make_pbr_mat(f"{name}_Frame", frame_color, metallic=0.6, rough=0.25)
    black_mat = make_pbr_mat("Bike_BlackSteel", (0.02, 0.02, 0.025), metallic=0.5, rough=0.4)
    rubber_mat = make_pbr_mat("Bike_Rubber", (0.02, 0.02, 0.02), rough=0.85)
    steel_mat = make_pbr_mat("Bike_Steel", (0.85, 0.85, 0.88), metallic=1.0, rough=0.20)

    def adopt(o, mat=None):
        if mat:
            o.data.materials.append(mat)
        o.parent = root
        return o

    def beam(b_name, p1, p2, r, mat, segs=12):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        bpy.ops.mesh.primitive_cylinder_add(vertices=segs, radius=r, depth=d.length, location=(p1 + p2) / 2)
        o = bpy.context.active_object
        o.name = f"{name}_{b_name}"
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
        link_only_to(o, target_col)
        return adopt(o, mat)

    def cyl_y(c_name, loc, r, length, mat, segs=24):
        bpy.ops.mesh.primitive_cylinder_add(vertices=segs, radius=r, depth=length, location=loc, rotation=(pi / 2, 0, 0))
        o = bpy.context.active_object
        o.name = f"{name}_{c_name}"
        link_only_to(o, target_col)
        return adopt(o, mat)

    # Frame geometry
    AXLE_Z = 0.33
    REAR_X, FRONT_X = -0.52, 0.56
    BB = Vector((0.0, 0.0, 0.30))
    SEAT_TOP = Vector((-0.18, 0.0, 0.78))
    HT_BOT = Vector((0.45, 0.0, 0.68))
    HT_TOP = Vector((0.40, 0.0, 0.82))

    beam("Seat_Tube", BB, SEAT_TOP, 0.020, frame_mat)
    beam("Top_Tube", Vector((-0.17, 0, 0.76)), Vector((0.41, 0, 0.78)), 0.021, frame_mat)
    beam("Down_Tube", BB, Vector((0.43, 0, 0.71)), 0.028, frame_mat)
    beam("Head_Tube", HT_BOT, HT_TOP, 0.030, frame_mat)

    for s in (-1, 1):
        beam(f"Seat_Stay_{s}", Vector((-0.175, s * 0.035, 0.74)), Vector((REAR_X, s * 0.055, AXLE_Z)), 0.010, frame_mat)
        beam(f"Chain_Stay_{s}", Vector((0.0, s * 0.035, 0.30)), Vector((REAR_X, s * 0.055, AXLE_Z)), 0.012, frame_mat)

    # Wheels (26")
    R_TIRE = 0.33
    for tag, x in (("Wheel_F", FRONT_X), ("Wheel_R", REAR_X)):
        cyl_y(f"{tag}_Tire", (x, 0, AXLE_Z), R_TIRE, 0.052, rubber_mat, segs=32)
        cyl_y(f"{tag}_Rim", (x, 0, AXLE_Z), R_TIRE * 0.88, 0.035, black_mat, segs=24)
        cyl_y(f"{tag}_Hub", (x, 0, AXLE_Z), 0.028, 0.09, steel_mat, segs=16)

    # Handlebars & Stem
    u = (HT_TOP - HT_BOT).normalized()
    T = HT_TOP + u * 0.09
    BAR_C = T + Vector((0.075, 0, 0.012))
    beam("Stem", T, BAR_C, 0.016, black_mat)
    beam("Bar", BAR_C + Vector((0, -0.32, 0)), BAR_C + Vector((0, 0.32, 0)), 0.012, black_mat)

    # Saddle
    beam("Seat_Post", SEAT_TOP, Vector((-0.21, 0, 0.90)), 0.014, steel_mat)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.24, 0, 0.92))
    sad = bpy.context.active_object
    sad.name = f"{name}_Saddle"
    sad.scale = (0.24, 0.14, 0.04)
    link_only_to(sad, target_col)
    adopt(sad, black_mat)

    # Kickstand (leaning slightly)
    beam("Kickstand", BB + Vector((-0.1, -0.04, 0)), BB + Vector((-0.18, -0.22, -0.30)), 0.01, black_mat)

    root.location = location
    root.rotation_euler = (0, 0, rot_z)
    return root


# ----------------------------------------------------------------------------
# 6. SEMINAR HALL INTERIOR BUILDER
# ----------------------------------------------------------------------------
def build_seminar_hall(target_col, origin=(14.2, 4.2, 4.30)):
    print("--- Building Seminar Hall Interior on First Floor with Vivid Colors ---")
    x0, y0, z0 = origin

    wood_l = make_pbr_mat("SH_WoodLight", (0.78, 0.58, 0.36), rough=0.50)
    wood_d = make_pbr_mat("SH_WoodDark", (0.42, 0.24, 0.12), rough=0.55)
    red_mat = make_pbr_mat("SH_SeatRed", (0.85, 0.04, 0.05), rough=0.80)
    stage_mat = make_pbr_mat("SH_StageFloor", (0.82, 0.68, 0.52), rough=0.55)
    screen_mat = make_pbr_mat("SH_Screen", (0.96, 0.98, 1.0), rough=0.25, emit=(0.96, 0.98, 1.0), emit_strength=2.5)
    banner_mat = make_pbr_mat("SH_BannerRed", (0.72, 0.03, 0.04), rough=0.70)
    frame_mat = make_pbr_mat("SH_Frame", (0.02, 0.02, 0.03), rough=0.40)
    dark_mat = make_pbr_mat("SH_DarkPlastic", (0.03, 0.03, 0.035), rough=0.50)
    chrome_mat = make_pbr_mat("SH_Chrome", (0.92, 0.92, 0.94), metallic=1.0, rough=0.15)
    podium_mat = make_pbr_mat("SH_PodiumWood", (0.72, 0.52, 0.32), rough=0.45)

    def add_box(b_name, loc, size, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = bpy.context.active_object
        o.name = b_name
        o.scale = size
        if mat:
            o.data.materials.append(mat)
        link_only_to(o, target_col)
        return o

    # 1. Stage platform at North side
    STAGE_W = 8.5
    STAGE_D = 2.2
    STAGE_H = 0.38
    stage_y = y0 + 2.7
    add_box("SH_Stage_Platform", (x0, stage_y, z0 + STAGE_H / 2), (STAGE_W, STAGE_D, STAGE_H), stage_mat)
    add_box("SH_Stage_Step", (x0, stage_y - STAGE_D / 2 - 0.25, z0 + STAGE_H / 4), (STAGE_W, 0.50, STAGE_H / 2), stage_mat)

    # 2. Projector Screen & Red Banners on North Wall
    SCREEN_W = 5.2
    SCREEN_H = 2.4
    screen_y = y0 + 3.85
    add_box("SH_Screen_Frame", (x0, screen_y, z0 + 2.4), (SCREEN_W + 0.2, 0.06, SCREEN_H + 0.2), frame_mat)
    add_box("SH_Screen_Surface", (x0, screen_y - 0.02, z0 + 2.4), (SCREEN_W, 0.03, SCREEN_H), screen_mat)
    for s in (-1, 1):
        add_box(f"SH_Banner_{s}", (x0 + s * (SCREEN_W / 2 + 0.65), screen_y - 0.01, z0 + 2.4), (0.9, 0.04, SCREEN_H), banner_mat)

    # 3. Speaker Podium on Stage
    pod_x = x0 - 2.8
    pod_y = stage_y - 0.3
    pod_z = z0 + STAGE_H
    add_box("SH_Podium_Base", (pod_x, pod_y, pod_z + 0.03), (0.65, 0.48, 0.06), podium_mat)
    add_box("SH_Podium_Col", (pod_x, pod_y, pod_z + 0.55), (0.40, 0.30, 0.98), podium_mat)
    add_box("SH_Podium_Top", (pod_x, pod_y, pod_z + 1.06), (0.75, 0.55, 0.06), podium_mat)

    # 4. Guest Chairs on Stage (5 chairs)
    for gi in range(5):
        gx = x0 - 1.8 + gi * 0.90
        gy = stage_y + 0.45
        gz = z0 + STAGE_H
        add_box(f"SH_GuestChair_Seat_{gi}", (gx, gy, gz + 0.24), (0.48, 0.46, 0.08), dark_mat)
        add_box(f"SH_GuestChair_Back_{gi}", (gx, gy + 0.21, gz + 0.55), (0.46, 0.05, 0.54), frame_mat)
        add_box(f"SH_GuestChair_Leg_{gi}", (gx, gy, gz + 0.12), (0.44, 0.42, 0.24), chrome_mat)

    # 5. Concentric Rows of Red Auditorium Seats
    ROWS = 4
    for r in range(ROWS):
        row_y = y0 + 0.6 - r * 1.05
        for s_idx, sx in enumerate([-4.2, -3.5, -2.8, -2.1, -1.4]):
            add_box(f"SH_Seat_{r}_L_{s_idx}", (x0 + sx, row_y, z0 + 0.22), (0.50, 0.45, 0.44), red_mat)
            add_box(f"SH_SeatBack_{r}_L_{s_idx}", (x0 + sx, row_y - 0.20, z0 + 0.56), (0.50, 0.08, 0.48), red_mat)
        for s_idx, sx in enumerate([1.4, 2.1, 2.8, 3.5, 4.2]):
            add_box(f"SH_Seat_{r}_R_{s_idx}", (x0 + sx, row_y, z0 + 0.22), (0.50, 0.45, 0.44), red_mat)
            add_box(f"SH_SeatBack_{r}_R_{s_idx}", (x0 + sx, row_y - 0.20, z0 + 0.56), (0.50, 0.08, 0.48), red_mat)

    # 6. Acoustic Wood Panelling along East & West walls
    for pi in range(5):
        py = y0 - 2.5 + pi * 1.3
        mat_p = wood_l if pi % 2 == 0 else wood_d
        add_box(f"SH_Panel_W_{pi}", (x0 - 5.85, py, z0 + 1.8), (0.05, 1.15, 3.2), mat_p)
        add_box(f"SH_Panel_E_{pi}", (x0 + 5.85, py, z0 + 1.8), (0.05, 1.15, 3.2), mat_p)

    print("Seminar Hall interior built successfully.")


# ----------------------------------------------------------------------------
# 7. ACADEMIC LIBRARY INTERIOR BUILDER
# ----------------------------------------------------------------------------
def build_library(target_col, origin=(-0.0, -4.5, 4.30)):
    print("--- Building Academic Library on First Floor with Vivid Colors ---")
    x0, y0, z0 = origin

    oak_mat = make_pbr_mat("Lib_Oak", (0.48, 0.28, 0.12), rough=0.45)
    oak_dark = make_pbr_mat("Lib_OakDark", (0.26, 0.14, 0.06), rough=0.55)
    table_mat = make_pbr_mat("Lib_TableWood", (0.72, 0.52, 0.32), rough=0.40)
    steel_mat = make_pbr_mat("Lib_Steel", (0.04, 0.04, 0.05), metallic=0.5, rough=0.4)
    chair_mat = make_pbr_mat("Lib_ChairCushion", (0.08, 0.18, 0.36), rough=0.65)

    def add_box(b_name, loc, size, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = bpy.context.active_object
        o.name = b_name
        o.scale = size
        if mat:
            o.data.materials.append(mat)
        link_only_to(o, target_col)
        return o

    # 1. Grand Bookshelf Walls along rear wall
    BOOK_PALETTE = [
        (0.75, 0.08, 0.08),  # Crimson Red
        (0.08, 0.22, 0.62),  # Royal Navy Blue
        (0.06, 0.42, 0.14),  # Forest Emerald
        (0.85, 0.58, 0.10),  # Golden Amber
        (0.48, 0.22, 0.10),  # Saddle Leather Brown
        (0.88, 0.85, 0.76),  # Antique Cream
        (0.05, 0.45, 0.48),  # Deep Teal
        (0.45, 0.08, 0.28),  # Burgundy Plum
        (0.20, 0.20, 0.22),  # Charcoal Cloth
        (0.92, 0.40, 0.08),  # Burnt Orange
    ]

    for wing, wx in (("West", -11.0), ("East", 11.0)):
        N_BAYS = 4
        BAY_W = 1.2
        PILASTER_W = 0.12
        UNIT_W = N_BAYS * (BAY_W + PILASTER_W) + PILASTER_W
        UNIT_H = 3.2
        by = y0 - 3.4

        # Back carcass
        add_box(f"Lib_Bookshelf_{wing}_Back", (wx, by, z0 + UNIT_H / 2), (UNIT_W, 0.04, UNIT_H), oak_dark)
        add_box(f"Lib_Bookshelf_{wing}_Top", (wx, by + 0.18, z0 + UNIT_H - 0.08), (UNIT_W, 0.38, 0.16), oak_mat)
        add_box(f"Lib_Bookshelf_{wing}_Base", (wx, by + 0.18, z0 + 0.22), (UNIT_W, 0.40, 0.44), oak_mat)

        # Pilasters
        for k in range(N_BAYS + 1):
            px = wx - UNIT_W / 2 + k * (BAY_W + PILASTER_W) + PILASTER_W / 2
            add_box(f"Lib_Pilaster_{wing}_{k}", (px, by + 0.18, z0 + UNIT_H / 2), (PILASTER_W, 0.42, UNIT_H), oak_mat)

        # Shelf Boards & Colorful Hardcover Books
        for b_idx in range(N_BAYS):
            bx = wx - UNIT_W / 2 + b_idx * (BAY_W + PILASTER_W) + PILASTER_W + BAY_W / 2
            for s_idx in range(5):
                sz = z0 + 0.44 + s_idx * 0.52
                add_box(f"Lib_Shelf_{wing}_{b_idx}_{s_idx}", (bx, by + 0.18, sz), (BAY_W, 0.36, 0.03), oak_mat)
                mat_book = make_pbr_mat(f"Lib_BookMat_{wing}_{b_idx}_{s_idx}", BOOK_PALETTE[(b_idx * 5 + s_idx) % len(BOOK_PALETTE)], rough=0.55)
                add_box(f"Lib_Books_{wing}_{b_idx}_{s_idx}", (bx, by + 0.18, sz + 0.18), (BAY_W * 0.88, 0.22, 0.32), mat_book)

    # 2. Reading Study Tables in Central & Side Bays
    study_table_positions = [
        (-8.0, y0), (-8.0, y0 + 1.8),
        (0.0, y0), (0.0, y0 + 1.8),
        (8.0, y0), (8.0, y0 + 1.8)
    ]
    for tid, (tx, ty) in enumerate(study_table_positions):
        # Table
        add_box(f"Lib_Table_{tid}", (tx, ty, z0 + 0.73), (2.4, 1.1, 0.04), table_mat)
        for lx in (-1.05, 1.05):
            for ly in (-0.45, 0.45):
                add_box(f"Lib_TableLeg_{tid}_{lx}_{ly}", (tx + lx, ty + ly, z0 + 0.36), (0.05, 0.05, 0.72), steel_mat)
        # 4 Study chairs per table
        for cid, (cx, cy) in enumerate([(-0.6, -0.75), (0.6, -0.75), (-0.6, 0.75), (0.6, 0.75)]):
            add_box(f"Lib_Chair_Seat_{tid}_{cid}", (tx + cx, ty + cy, z0 + 0.45), (0.44, 0.44, 0.06), chair_mat)
            add_box(f"Lib_Chair_Back_{tid}_{cid}", (tx + cx, ty + cy + (0.18 if cy < 0 else -0.18), z0 + 0.68), (0.42, 0.04, 0.40), chair_mat)
            add_box(f"Lib_Chair_Leg_{tid}_{cid}", (tx + cx, ty + cy, z0 + 0.22), (0.38, 0.38, 0.44), steel_mat)

    # 3. Interactive Information Display Panel at Library entrance
    panel_mat = make_pbr_mat("Lib_PanelScreen", (0.08, 0.38, 0.92), rough=0.20, emit=(0.08, 0.38, 0.92), emit_strength=2.2)
    add_box("Lib_Display_Kiosk_Base", (x0, y0 + 3.2, z0 + 0.05), (0.8, 0.6, 0.10), steel_mat)
    add_box("Lib_Display_Kiosk_Stand", (x0, y0 + 3.2, z0 + 0.60), (0.12, 0.12, 1.10), steel_mat)
    add_box("Lib_Display_Kiosk_Screen", (x0, y0 + 3.2, z0 + 1.45), (1.30, 0.08, 0.75), panel_mat)

    print("Academic Library built successfully.")


# ----------------------------------------------------------------------------
# 8. BADMINTON COURT & PARK BENCHES BUILDERS
# ----------------------------------------------------------------------------
def build_badminton_court(target_col, location=(38.0, 5.0, 0.02), rot_z=0.0):
    root = bpy.data.objects.new("Badminton_Court", None)
    link_only_to(root, target_col)

    FT = 0.3048
    HALF_L = 22.0 * FT
    HALF_W = 10.0 * FT
    SINGLES_HALF_W = 8.5 * FT
    POST_H = 5.08 * FT
    NET_CENTER_H = 5.0 * FT
    LINE_W = 0.04
    GREEN_MARGIN = 1.0

    wood_mat = make_pbr_mat("BC_WoodPlank", (0.76, 0.50, 0.26), rough=0.38)
    green_mat = make_pbr_mat("BC_CourtGreen", (0.04, 0.40, 0.12), rough=0.50)
    line_mat = make_pbr_mat("BC_LineWhite", (0.98, 0.98, 0.98), rough=0.35)
    post_mat = make_pbr_mat("BC_PostYellow", (0.96, 0.82, 0.06), metallic=0.2, rough=0.30)
    net_mat = make_pbr_mat("BC_NetWhite", (0.92, 0.92, 0.94), rough=0.70)

    def adopt(o, mat=None):
        if mat:
            o.data.materials.append(mat)
        o.parent = root
        return o

    def add_box(b_name, center, size, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=center)
        o = bpy.context.active_object
        o.name = b_name
        o.scale = size
        link_only_to(o, target_col)
        return adopt(o, mat)

    # Base apron and court surface
    tot_l = (HALF_L + GREEN_MARGIN) * 2
    tot_w = (HALF_W + GREEN_MARGIN) * 2
    add_box("BC_Surround", (0, 0, 0.01), (tot_l + 1.2, tot_w + 1.2, 0.02), wood_mat)
    add_box("BC_GreenSurface", (0, 0, 0.02), (tot_l, tot_w, 0.015), green_mat)

    # Court boundary lines
    add_box("BC_Line_Back_A", (-HALF_L, 0, 0.028), (LINE_W, HALF_W * 2, 0.005), line_mat)
    add_box("BC_Line_Back_B", (HALF_L, 0, 0.028), (LINE_W, HALF_W * 2, 0.005), line_mat)
    for s in (-1, 1):
        add_box(f"BC_Line_Side_{s}", (0, s * HALF_W, 0.028), (HALF_L * 2, LINE_W, 0.005), line_mat)
        add_box(f"BC_Line_Singles_{s}", (0, s * SINGLES_HALF_W, 0.028), (HALF_L * 2, LINE_W, 0.005), line_mat)
        add_box(f"BC_Line_ShortServ_{s}", (s * 6.5 * FT, 0, 0.028), (LINE_W, HALF_W * 2, 0.005), line_mat)

    # Net Posts and Net
    for s in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.035, depth=POST_H, location=(0, s * (HALF_W + 0.15), POST_H / 2))
        p = bpy.context.active_object
        p.name = f"BC_Post_{s}"
        link_only_to(p, target_col)
        adopt(p, post_mat)

    # Net mesh plane
    add_box("BC_Net_Mesh", (0, 0, NET_CENTER_H - 0.38), (0.015, (HALF_W + 0.15) * 2, 0.76), net_mat)
    add_box("BC_Net_Tape", (0, 0, NET_CENTER_H), (0.025, (HALF_W + 0.15) * 2, 0.06), line_mat)

    root.location = location
    root.rotation_euler = (0, 0, rot_z)
    return root


def build_park_bench(target_col, location, rot_z=0.0, name="Park_Bench"):
    root = bpy.data.objects.new(name, None)
    link_only_to(root, target_col)

    iron_mat = make_pbr_mat("Bench_CastIron", (0.025, 0.025, 0.03), metallic=0.7, rough=0.4)
    wood_mat = make_pbr_mat("Bench_WoodSlat", (0.58, 0.22, 0.08), rough=0.45)

    def adopt(o, mat=None):
        if mat:
            o.data.materials.append(mat)
        o.parent = root
        return o

    def add_box(b_name, loc, size, mat, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
        o = bpy.context.active_object
        o.name = f"{name}_{b_name}"
        o.scale = size
        link_only_to(o, target_col)
        return adopt(o, mat)

    BENCH_LEN = 1.8
    # 3 Seat wooden slats
    for si, sy in enumerate([-0.14, 0.0, 0.14]):
        add_box(f"SeatSlat_{si}", (0, sy, 0.44), (BENCH_LEN, 0.12, 0.035), wood_mat)
    # 2 Back wooden slats
    for bi, (by, bz) in enumerate([(0.22, 0.62), (0.26, 0.76)]):
        add_box(f"BackSlat_{bi}", (0, by, bz), (BENCH_LEN, 0.12, 0.035), wood_mat, rot=(radians(14), 0, 0))
    # Cast iron side legs & armrests
    for s in (-0.78, 0.78):
        add_box(f"LegFront_{s}", (s, -0.16, 0.22), (0.06, 0.06, 0.44), iron_mat)
        add_box(f"LegRear_{s}", (s, 0.24, 0.38), (0.06, 0.06, 0.76), iron_mat, rot=(radians(14), 0, 0))
        add_box(f"ArmRest_{s}", (s, 0.04, 0.58), (0.06, 0.44, 0.04), iron_mat)

    root.location = location
    root.rotation_euler = (0, 0, rot_z)
    return root


# ----------------------------------------------------------------------------
# MAIN EXECUTION
# ----------------------------------------------------------------------------
def main():
    print("==================================================")
    print("STARTING INTEGRATION OF NEW CAMPUS ASSETS (VIVID COLORS)")
    print("==================================================")

    # 1. Cleanup
    cleanup_old_assets()

    # Get target collections
    col_veg = get_or_create_col("Vegetation")
    col_props = get_or_create_col("Props_Vehicles")
    col_furn = get_or_create_col("Interior_Furniture")

    # 2. Plant Realistic Oak Trees (broad-crowned procedural oak trees)
    print("--- Generating Realistic Oak Trees ---")
    tree_specs = [
        # Arrival Plaza / West Lawns
        ((-30.0, 48.0, 0.0), 1.05, 11),
        ((-38.0, 58.0, 0.0), 0.95, 17),
        ((-22.0, 58.0, 0.0), 1.00, 23),
        ((-15.0, 42.0, 0.0), 0.90, 29),
        # East Boundary Lawns
        ((22.0, 60.0, 0.0), 1.00, 31),
        ((32.0, 62.0, 0.0), 1.10, 37),
        ((42.0, 54.0, 0.0), 0.95, 41),
        # Rear Greenway (Y = -22.0 ensures 13.5m clearance from building wall at Y = -8.5!)
        ((-14.0, -22.0, 0.0), 1.00, 43),
        ((0.0, -22.0, 0.0), 1.05, 47),
        ((14.0, -22.0, 0.0), 1.00, 53),
        # Flank Lawns
        ((-34.0, -4.0, 0.0), 1.00, 59),
        ((34.0, -4.0, 0.0), 1.00, 61),
    ]
    for idx, (loc, sc, s_seed) in enumerate(tree_specs):
        build_oak_tree(col_veg, loc, scale=sc, seed=s_seed, name_prefix=f"Oak_Tree_{idx+1}")
        print(f"  Planted Oak_Tree_{idx+1} at {loc}")

    # 3. Build Tensile Parking Shades (for Cars & Two-Wheelers)
    print("--- Building Tensile Parking Shades ---")
    build_parking_shade(col_props, location=(31.0, 40.0, 0.04), rot_z=0.0, bays=4, bay_span=4.5, name="Car_Parking_Shade")
    build_parking_shade(col_props, location=(22.0, 51.0, 0.04), rot_z=0.0, bays=2, bay_span=3.5, name="Bike_Parking_Shade")

    # 4. Build Procedural Corvette Z06 Supercars with Vivid Factory Paint
    print("--- Generating Corvette Z06 Supercars in Parking Bays ---")
    car_specs = [
        ((33.25, 36.5, 0.04), pi / 2, (0.82, 0.02, 0.03), "Corvette_Z06_TorchRed"),
        ((37.75, 36.5, 0.04), pi / 2, (0.95, 0.76, 0.02), "Corvette_Z06_VelocityYellow"),
        ((42.25, 36.5, 0.04), pi / 2, (0.94, 0.95, 0.97), "Corvette_Z06_CeramicWhite"),
        ((46.75, 36.5, 0.04), pi / 2, (0.01, 0.22, 0.72), "Corvette_Z06_ElkhartBlue"),
    ]
    for loc, rz, colr, cname in car_specs:
        build_corvette_z06(col_props, location=loc, rot_z=rz, paint_color=colr, name=cname)
        print(f"  Parked {cname} at {loc}")

    # 5. Build Mountain Bikes in Two-Wheeler Station with Vibrant Frame Finishes
    print("--- Generating Mountain Bikes in Bike Station ---")
    bike_colors = [
        (1.0, 0.32, 0.02),   # High-vis Neon Orange
        (0.0, 0.72, 0.85),   # Electric Cyan Turquoise
        (0.90, 0.05, 0.05),  # Racing Crimson Red
        (0.03, 0.03, 0.035), # Stealth Satin Black
        (0.28, 0.85, 0.08),  # Acid Lime Green
        (0.98, 0.80, 0.05),  # Sunburst Gold Yellow
    ]
    for bi in range(6):
        bx = 23.2 + bi * 0.95
        by = 48.0
        build_mountain_bike(col_props, location=(bx, by, 0.04), rot_z=pi / 2, frame_color=bike_colors[bi % len(bike_colors)], name=f"Mountain_Bike_{bi+1}")

    # 6. Build Seminar Hall on First Floor
    build_seminar_hall(col_furn, origin=(14.2, 4.2, 4.30))

    # 7. Build Academic Library on First Floor
    build_library(col_furn, origin=(0.0, -4.2, 4.30))

    # 8. Build Badminton Court in Sports Complex
    print("--- Building Badminton Court ---")
    build_badminton_court(col_props, location=(38.0, 5.0, 0.02), rot_z=0.0)

    # 9. Build Park Benches along walkways and plazas
    print("--- Building Park Benches ---")
    bench_positions = [
        ((-4.5, 42.0, 0.04), pi / 2),
        ((4.5, 42.0, 0.04), -pi / 2),
        ((-12.0, 28.0, 0.04), 0.0),
        ((12.0, 28.0, 0.04), 0.0),
        ((26.0, 14.0, 0.04), pi / 2),
        ((26.0, 22.0, 0.04), pi / 2),
    ]
    for bi, (bloc, brz) in enumerate(bench_positions):
        build_park_bench(col_props, location=bloc, rot_z=brz, name=f"Park_Bench_{bi+1}")

    # 10. Configure 3D Viewport Shading for Full Material Display
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'

    # 11. Save Blend File
    blend_path = bpy.data.filepath
    if not blend_path:
        blend_path = r"c:\Users\krish\.gemini\antigravity-ide\scratch\IMRD-Blender-Game\output\imrd_campus.blend"
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"SUCCESS! Campus scene with vivid colors saved cleanly to {blend_path}")


if __name__ == "__main__":
    main()
