"""
Seminar Hall generator for Blender (works on Blender 3.x / 4.x)

HOW TO RUN
  1. Open Blender -> "Scripting" workspace -> New -> paste this file -> Run Script (Alt+P)
  2. Or from terminal:  blender --python seminar_hall_blender.py

WHAT IT BUILDS
  * Hall with wood-panel walls, ceiling with red beams + recessed lights   (image 1)
  * Curved rows of RED audience seats with arm-rests and a centre aisle    (image 1)
  * Stage with steps, projector screen, red banners, spot-light bar        (image 2)
  * Wooden speaker podium with microphone                                  (image 3)
  * 5 guest/speaker chairs (mesh back + chrome cantilever frame) on stage  (image 4)
  * Lights, camera and render settings

Units: metres. Stage wall is at y = 0, audience looks toward -Y.
"""

import bpy
import math
from mathutils import Vector

# ----------------------------------------------------------------------------
# CONFIG  (change these to resize / re-style the hall)
# ----------------------------------------------------------------------------
HALL_W = 24.0          # width  (X)
HALL_L = 26.0          # length (Y)
HALL_H = 7.0           # height (Z)

STAGE_DEPTH = 6.0
STAGE_H = 0.6

ROWS = 11              # number of audience rows
FIRST_ROW_R = 9.0      # radius of first row from arc centre
ROW_SPACING = 1.0
ARC_HALF_ANGLE = 32    # degrees each side of centre
SEAT_PITCH = 0.62      # centre-to-centre seat distance
AISLE_HALF_WIDTH = 0.75
ARC_CENTER = Vector((0.0, 2.0, 0.0))

GUEST_CHAIRS = 5


# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------
def clean_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def make_mat(name, color, rough=0.5, metallic=0.0, emission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    if emission > 0:
        # works in both 3.x ("Emission") and 4.x ("Emission Color")
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = (*color, 1)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission
    m.diffuse_color = (*color, 1)
    return m


def box(name, loc, dims, mat, rot=(0, 0, 0)):
    """Cube centred at loc with full size dims=(x,y,z)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = dims
    o.rotation_euler = rot
    o.data.materials.append(mat)
    return o


def tube(name, p1, p2, radius, mat, verts=16):
    """Cylinder going from point p1 to point p2."""
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=d.length,
                                        location=(p1 + p2) / 2, vertices=verts)
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


def sphere(name, loc, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=16, ring_count=8)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return o


def linked_copy(src, name, loc, rot_z):
    c = src.copy()            # shares mesh data -> light on memory
    c.name = name
    c.location = loc
    c.rotation_euler = (0, 0, rot_z)
    bpy.context.collection.objects.link(c)
    return c


# ----------------------------------------------------------------------------
# MATERIALS
# ----------------------------------------------------------------------------
M = {}
def build_materials():
    M['carpet']   = make_mat("Carpet",      (0.55, 0.57, 0.62), 0.95)
    M['wood_l']   = make_mat("WoodLight",   (0.72, 0.55, 0.36), 0.55)
    M['wood_d']   = make_mat("WoodDark",    (0.50, 0.35, 0.22), 0.55)
    M['wall_top'] = make_mat("WallBeige",   (0.80, 0.70, 0.56), 0.8)
    M['ceiling']  = make_mat("Ceiling",     (0.85, 0.82, 0.78), 0.9)
    M['red']      = make_mat("SeatRed",     (0.75, 0.04, 0.05), 0.85)
    M['red_beam'] = make_mat("BeamRed",     (0.55, 0.05, 0.04), 0.6)
    M['dark']     = make_mat("DarkPlastic", (0.04, 0.04, 0.05), 0.5)
    M['stage']    = make_mat("StageFloor",  (0.78, 0.84, 0.92), 0.6)
    M['step']     = make_mat("StageStep",   (0.62, 0.72, 0.85), 0.6)
    M['screen']   = make_mat("Screen",      (0.95, 0.97, 1.0), 0.4, emission=1.2)
    M['frame']    = make_mat("ScreenFrame", (0.02, 0.02, 0.03), 0.4)
    M['lamp']     = make_mat("LampPanel",   (1.0, 0.95, 0.85), 0.3, emission=12.0)
    M['glass']    = make_mat("Glass",       (0.25, 0.35, 0.45), 0.1, 0.0)
    M['chrome']   = make_mat("Chrome",      (0.9, 0.9, 0.92), 0.12, 1.0)
    M['mesh_w']   = make_mat("MeshWhite",   (0.85, 0.85, 0.87), 0.7)
    M['mesh_b']   = make_mat("MeshBlack",   (0.03, 0.03, 0.03), 0.8)
    M['mic']      = make_mat("Mic",         (0.02, 0.02, 0.02), 0.3, 0.6)


# ----------------------------------------------------------------------------
# HALL SHELL
# ----------------------------------------------------------------------------
def build_hall():
    hw, hl, hh = HALL_W, HALL_L, HALL_H
    # floor + ceiling
    box("Floor",   (0, hl / 2, -0.05), (hw, hl, 0.1), M['carpet'])
    box("Ceiling", (0, hl / 2, hh + 0.05), (hw, hl, 0.1), M['ceiling'])

    # walls (thick slabs)
    t = 0.2
    box("Wall_Stage", (0, -t / 2, hh / 2), (hw, t, hh), M['wall_top'])
    box("Wall_Back",  (0, hl + t / 2, hh / 2), (hw, t, hh), M['wall_top'])
    box("Wall_Left",  (-hw / 2 - t / 2, hl / 2, hh / 2), (t, hl, hh), M['wall_top'])
    box("Wall_Right", (hw / 2 + t / 2, hl / 2, hh / 2), (t, hl, hh), M['wall_top'])

    # wood panelling on side walls + back wall
    i = 0
    y = 0.8
    while y < hl - 0.5:
        mat = M['wood_l'] if i % 2 == 0 else M['wood_d']
        for sx in (-1, 1):
            box(f"Panel_Side_{i}_{sx}", (sx * (hw / 2 - 0.04), y, 2.6), (0.08, 1.5, 4.2), mat)
        y += 1.6
        i += 1
    x = -hw / 2 + 1.0
    i = 0
    while x < hw / 2 - 0.5:
        mat = M['wood_l'] if i % 2 == 0 else M['wood_d']
        box(f"Panel_Back_{i}", (x, hl - 0.04, 2.6), (1.5, 0.08, 4.2), mat)
        x += 1.6
        i += 1
    # skirting / dado
    for sx in (-1, 1):
        box(f"Dado_{sx}", (sx * (hw / 2 - 0.05), hl / 2, 0.25), (0.1, hl, 0.5), M['wood_d'])

    # high windows on right wall (like image 1)
    for k in range(4):
        box(f"Window_{k}", (hw / 2 - 0.03, 5 + k * 5.5, 5.7), (0.06, 3.0, 1.0), M['glass'])

    # ceiling: red beams + recessed light panels
    for k, yy in enumerate((5.0, 11.0, 17.0, 23.0)):
        box(f"Beam_{k}", (0, yy, hh - 0.25), (hw, 0.8, 0.5), M['red_beam'])
    for ky, yy in enumerate((2.0, 8.0, 14.0, 20.0)):
        for kx, xx in enumerate((-7.0, 0.0, 7.0)):
            box(f"CeilLight_{ky}_{kx}", (xx, yy, hh - 0.02), (2.2, 2.2, 0.04), M['lamp'])


# ----------------------------------------------------------------------------
# STAGE, SCREEN, PODIUM
# ----------------------------------------------------------------------------
def build_stage():
    w = HALL_W - 2.0
    box("Stage", (0, STAGE_DEPTH / 2, STAGE_H / 2), (w, STAGE_DEPTH, STAGE_H), M['stage'])
    box("Step_1", (0, STAGE_DEPTH + 0.5, 0.2), (w, 1.0, 0.4), M['step'])
    box("Step_2", (0, STAGE_DEPTH + 1.5, 0.1), (w, 1.0, 0.2), M['step'])

    # projector screen + frame
    box("Screen_Frame", (0, 0.06, 3.5), (6.4, 0.08, 3.7), M['frame'])
    box("Screen", (0, 0.12, 3.5), (6.0, 0.05, 3.3), M['screen'])
    # red banners either side
    for sx in (-1, 1):
        box(f"Banner_{sx}", (sx * 4.3, 0.08, 3.5), (1.0, 0.05, 3.3), M['red'])
        box(f"BannerTrim_{sx}", (sx * 4.3, 0.1, 3.5), (1.1, 0.03, 3.4), M['frame'])

    # spot-light bar above stage
    box("LightBar", (0, 2.2, 6.2), (8.0, 0.12, 0.12), M['frame'])
    for k in range(6):
        xx = -3.5 + k * 1.4
        tube(f"Spot_{k}", (xx, 2.2, 6.1), (xx, 2.9, 5.7), 0.16, M['dark'])
        sphere(f"SpotLens_{k}", (xx, 2.95, 5.68), 0.12, M['lamp'])


def build_podium(x=-7.0, y=3.6):
    z0 = STAGE_H
    parts = [
        box("Pod_Base",   (0, 0, z0 + 0.03), (0.70, 0.50, 0.06), M['wood_l']),
        box("Pod_Column", (0, 0, z0 + 0.58), (0.42, 0.32, 1.05), M['wood_l']),
        box("Pod_Top",    (0, 0.0, z0 + 1.13), (0.80, 0.58, 0.06), M['wood_l'], rot=(math.radians(-8), 0, 0)),
        tube("Pod_Neck",  (0.0, 0.05, z0 + 1.15), (0.0, 0.05, z0 + 1.50), 0.01, M['mic']),
        tube("Pod_Mic",   (0.0, 0.05, z0 + 1.50), (0.0, 0.17, z0 + 1.55), 0.014, M['mic']),
    ]
    p = join(parts, "Podium")
    p.location = (x, y, 0)
    p.rotation_euler = (0, 0, 0)       # front faces +Y (audience)
    return p


# ----------------------------------------------------------------------------
# CHAIRS
# ----------------------------------------------------------------------------
def make_audience_seat_proto():
    """Red theatre seat. Front faces +Y, back at -Y. Origin at floor."""
    parts = [
        box("S_Pedestal", (0, 0, 0.20), (0.40, 0.40, 0.40), M['dark']),
        box("S_Cushion",  (0, 0.02, 0.46), (0.50, 0.48, 0.12), M['red']),
        box("S_Back",     (0, -0.26, 0.88), (0.50, 0.10, 0.66), M['red'], rot=(math.radians(10), 0, 0)),
        box("S_ArmL",     (-0.275, 0.0, 0.66), (0.07, 0.50, 0.05), M['dark']),
        box("S_ArmR",     (0.275, 0.0, 0.66), (0.07, 0.50, 0.05), M['dark']),
        box("S_SideL",    (-0.275, -0.02, 0.33), (0.04, 0.46, 0.66), M['red']),
        box("S_SideR",    (0.275, -0.02, 0.33), (0.04, 0.46, 0.66), M['red']),
    ]
    s = join(parts, "AudienceSeat_Proto")
    return s


def build_audience():
    proto = make_audience_seat_proto()
    proto.hide_viewport = False
    count = 0
    for row in range(ROWS):
        r = FIRST_ROW_R + row * ROW_SPACING
        half = math.radians(ARC_HALF_ANGLE)
        n = int((2 * half * r) / SEAT_PITCH)
        for k in range(n + 1):
            t = -half + k * (2 * half / n)          # angle from centre line
            x = ARC_CENTER.x + r * math.sin(t)
            y = ARC_CENTER.y + r * math.cos(t)
            if abs(x) < AISLE_HALF_WIDTH:           # centre aisle
                continue
            rot_z = math.pi - t                     # face the stage
            linked_copy(proto, f"Seat_{row}_{k}", (x, y, 0), rot_z)
            count += 1
    # remove the prototype (copies keep sharing its mesh data)
    bpy.data.objects.remove(proto, do_unlink=True)
    print(f"Audience seats created: {count}")


def make_guest_chair_proto():
    """Cantilever chrome chair with mesh back (image 4). Front faces +Y."""
    C, B, W = M['chrome'], M['mesh_b'], M['mesh_w']
    seat_z = 0.46
    parts = [box("G_Seat", (0, 0, seat_z), (0.50, 0.50, 0.08), B)]

    # backrest: white mesh with black horizontal bands
    parts.append(box("G_BackFrame", (0, -0.26, 0.86), (0.48, 0.03, 0.62), W, rot=(math.radians(8), 0, 0)))
    for k in range(5):
        zz = 0.62 + k * 0.12
        yy = -0.26 - (zz - 0.86) * math.tan(math.radians(8)) * -1
        parts.append(box(f"G_Band_{k}", (0, yy - 0.002, zz), (0.49, 0.035, 0.045), B,
                         rot=(math.radians(8), 0, 0)))

    for sx in (-1, 1):
        x = sx * 0.25
        # armrest + support
        parts.append(box(f"G_Arm_{sx}", (sx * 0.27, 0.02, 0.66), (0.06, 0.34, 0.045), B))
        parts.append(tube(f"G_ArmPost_{sx}", (x + sx * 0.02, 0.15, 0.46), (x + sx * 0.02, 0.15, 0.64), 0.012, C))
        # chrome cantilever frame (floor runner -> front leg -> seat rail -> back post)
        parts.append(tube(f"G_Runner_{sx}",  (x, -0.32, 0.03), (x, 0.30, 0.03), 0.014, C))
        parts.append(tube(f"G_FrontLeg_{sx}", (x, 0.30, 0.03), (x, 0.24, 0.43), 0.014, C))
        parts.append(tube(f"G_Rail_{sx}",    (x, 0.24, 0.43), (x, -0.22, 0.43), 0.014, C))
        parts.append(tube(f"G_BackPost_{sx}", (x, -0.22, 0.43), (x, -0.30, 0.90), 0.014, C))
        parts.append(tube(f"G_BackLeg_{sx}", (x, -0.32, 0.03), (x, -0.25, 0.30), 0.014, C))
    parts.append(tube("G_CrossBar", (-0.25, -0.32, 0.03), (0.25, -0.32, 0.03), 0.014, C))
    return join(parts, "GuestChair_Proto")


def build_guest_chairs():
    proto = make_guest_chair_proto()
    spacing = 1.4
    start_x = -(GUEST_CHAIRS - 1) * spacing / 2 + 2.0
    for k in range(GUEST_CHAIRS):
        linked_copy(proto, f"GuestChair_{k}", (start_x + k * spacing, 3.4, STAGE_H), 0)
    bpy.data.objects.remove(proto, do_unlink=True)


# ----------------------------------------------------------------------------
# LIGHTS / CAMERA / RENDER
# ----------------------------------------------------------------------------
def add_area_light(name, loc, energy, size, color=(1, 0.94, 0.85)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    bpy.context.collection.objects.link(lo)
    return lo


def build_lights_camera():
    # hall lighting
    for yy in (2.0, 8.0, 14.0, 20.0):
        for xx in (-7.0, 0.0, 7.0):
            add_area_light(f"Light_{xx}_{yy}", (xx, yy, HALL_H - 0.3), 900, 2.5)
    # stage wash
    add_area_light("StageWash", (0, 3.5, 6.0), 2500, 6.0, (1.0, 0.97, 0.9))

    # world
    w = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.02, 0.02, 0.03, 1)
    bg.inputs[1].default_value = 0.5

    # camera at the back of the hall, looking at the stage
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 22
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (8.5, HALL_L - 1.0, 4.2)
    target = Vector((-1.0, 4.0, 1.8))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    clean_scene()
    build_materials()
    build_hall()
    build_stage()
    build_podium()
    build_guest_chairs()
    build_audience()
    build_lights_camera()
    print("Seminar hall created. Press Numpad-0 for the camera view.")


main()
