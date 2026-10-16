"""
game_config.py
==============
Single source of truth for IMRD campus geometry (Phase 2).

Conventions
-----------
* 1 Blender unit == 1 metre (scene unit scale 1.0, METRIC).
* Z is up. +Y is the FRONT of the main academic building (plaza, road, gate);
  -Y is the back. X runs left(-)/right(+) when facing the building from +Y.
* Elevations are absolute world Z in metres.

ASSUMPTIONS (no verified IMRD drawings/photos exist in the project)
-------------------------------------------------------------------
Every dimension below is an *approximation* chosen for believable human scale
and kept compatible with the original blockout (footprint 41.2 x 17.0 m, floor
to floor ~4 m, entrance on the +Y facade). None are surveyed IMRD values.
Interior room layout (lobby, two front classrooms, rear common hall) is an
assumed layout derived from the original partition walls.

Pure data module: it must not import bpy.
"""

UNITS_PER_METER = 1.0

# ----------------------------------------------------------------------
# Elevations and slabs
# ----------------------------------------------------------------------
GROUND_Z = 0.0
PLAZA_Z = 0.055            # top of paved plaza (approx.)
PLINTH_TOP_Z = 0.30        # top of building plinth
FLOOR_G_Z = 0.34           # walkable finished floor, ground floor
SLAB_G_THICK = 0.04        # tile finish on plinth
FLOOR_1_Z = 4.30           # walkable finished floor, first floor
SLAB_1_THICK = 0.30
G_CEILING_Z = FLOOR_1_Z - SLAB_1_THICK     # 4.00 underside of first-floor slab
ROOF_BOTTOM_Z = 8.30
ROOF_THICK = 0.30
ROOF_TOP_Z = ROOF_BOTTOM_Z + ROOF_THICK    # 8.60
PARAPET_H = 1.0

FLOORS = {"G": FLOOR_G_Z, "1": FLOOR_1_Z}
# Exterior wall vertical extents per floor; interior walls start at the floor finish
EXT_WALL_Z = {"G": (PLINTH_TOP_Z, G_CEILING_Z), "1": (FLOOR_1_Z, ROOF_BOTTOM_Z)}
INT_WALL_Z = {"G": (FLOOR_G_Z, G_CEILING_Z), "1": (FLOOR_1_Z, ROOF_BOTTOM_Z)}

# ----------------------------------------------------------------------
# Walls / footprint
# ----------------------------------------------------------------------
EXT_WALL_T = 0.30
INT_WALL_T = 0.20
EXT_CENTER_X = 20.5        # exterior wall centre lines (+/-)
EXT_CENTER_Y = 8.5
BLD_OUT_X = EXT_CENTER_X + EXT_WALL_T / 2      # 20.65 outer face
BLD_OUT_Y = EXT_CENTER_Y + EXT_WALL_T / 2      # 8.65
BLD_IN_X = EXT_CENTER_X - EXT_WALL_T / 2       # 20.35 inner face
BLD_IN_Y = EXT_CENTER_Y - EXT_WALL_T / 2       # 8.35
PLINTH_HALF = (20.8, 8.8)
SLAB_1_HALF = (20.8, 8.8)
ROOF_HALF = (20.9, 8.9)
PARTITION_Y = 0.0          # corridor/partition wall separating front rooms from rear hall
CLASS_WALL_X = 8.0         # walls separating lobby from the two front classrooms

# ----------------------------------------------------------------------
# Doors (leaf hung on the hinge-side jamb) and openings
# ----------------------------------------------------------------------
DOOR_OPENING_W = 1.10
DOOR_OPENING_H = 2.20
DOOR_FRAME_W = 0.05
DOOR_LEAF_W = 0.96         # hinge sits frame + leaf/2 + gap from the opening edge so the
                           # rotated leaf clears the jamb; leaf end stays inside the far jamb
DOOR_HINGE_GAP = 0.005
DOOR_LEAF_H = 2.10         # < opening - frame (2.15)
DOOR_LEAF_T = 0.045
DOOR_BOTTOM_CLEARANCE = 0.01
DOOR_OPEN_DEG = 90.0

ENTRANCE_OPENING_W = 3.60
ENTRANCE_OPENING_H = 2.60  # above FLOOR_G_Z
ENTRANCE_FRAME_W = 0.06
ENTRANCE_LEAF_W = 1.70     # two leaves, ~0.02 m gap between them at the centre
ENTRANCE_LEAF_H = 2.45
ENTRANCE_LEAF_T = 0.05
ENTRANCE_X = 0.0

ARCH_FRAME_W = 0.05

WINDOW_W = 2.40
WINDOW_H = 1.50
WINDOW_SILL_H = 1.00       # above floor finish
WINDOW_FRAME_W = 0.05
WINDOW_GLASS_T = 0.04
WINDOW_FRAME_PROUD = 0.04  # frames project this much beyond the wall faces (total)

WING_WINDOW_X = (11.5, 15.0, 18.5)      # mirrored for left wing
BACK_WINDOW_X = (-15.0, -5.0, 5.0, 15.0)
SIDE_WINDOW_Y = (4.2, -4.0)

HEADROOM = 2.0             # minimum clear height above any walking surface
PLAYER_HEIGHT = 1.75       # approx., student avatar
SPAWN = (0.0, 68.0, 0.0)   # unchanged from original player controller
ENTRANCE_POINT = (0.0, 8.5, FLOOR_G_Z)

# ----------------------------------------------------------------------
# Staircase (ground -> first floor), runs toward -Y inside the lobby
# ----------------------------------------------------------------------
STAIR_X = 5.0
STAIR_W = 1.8
STAIR_RISE = FLOOR_1_Z - FLOOR_G_Z          # 3.96
STAIR_RISER_COUNT = 22
STAIR_RISER_H = STAIR_RISE / STAIR_RISER_COUNT   # 0.18
STAIR_TREAD_D = 0.28
STAIR_TREAD_COUNT = STAIR_RISER_COUNT - 1   # the upper floor edge is the last "tread"
STAIR_Y_START = 7.30                         # front face of first riser
STAIR_Y_TOP = STAIR_Y_START - STAIR_TREAD_COUNT * STAIR_TREAD_D   # 1.42
STAIR_RAIL_H = 0.90
# opening in first-floor slab (clears run + 0.1 m each side)
STAIR_OPEN_X = (STAIR_X - STAIR_W / 2 - 0.2, STAIR_X + STAIR_W / 2 + 0.2)
STAIR_OPEN_Y = (STAIR_Y_TOP, STAIR_Y_START + 0.20)
# top landing = upper floor between the stair top edge and the partition wall
TOP_LANDING_Y = (PARTITION_Y + INT_WALL_T / 2, STAIR_Y_TOP)
# bottom landing = ground floor between the first riser and the front wall
BOTTOM_LANDING_Y = (STAIR_Y_START, BLD_IN_Y)

# ----------------------------------------------------------------------
# Naming
# ----------------------------------------------------------------------
OWNER_KEY = "imrd_owner"
OWNER_VALUE = "campus_builder"

COLLECTIONS = {
    "terrain": "Terrain_Roads",
    "architecture": "Building_Structure",
    "interior_arch": "Interior_Architecture",
    "furniture": "Interior_Furniture",
    "props": "Props_Vehicles",
    "vegetation": "Vegetation",
    "gate": "Gate_Boundary",
    "lighting": "Lighting_Cameras",
    "collision": "Collision_Proxies",     # populated in the physics phase
    "gameplay": "Gameplay_Objects",       # doors etc.
}

PREFIX = {
    "wall": "Wall_", "slab": "Slab_", "frame": "Frame_", "glass": "Glass_",
    "door": "Door_", "stair": "Stair_", "rail": "Rail_", "landing": "Landing_",
}

# Gameplay-stable names other modules rely on
ENTRANCE_DOOR_NAME = "Interactive_Entrance_Door"   # used by 03/run_game
ENTRANCE_DOOR_B_NAME = "Door_Entrance_B"
ENTRANCE_DOOR_ID = "door_main"
CAMERA_OVERVIEW = "Cam_Overview"
CAMERA_ENTRANCE = "Cam_Entrance"
CAMERA_GATE = "Cam_Gate"
STABLE_OBJECT_NAMES = (
    ENTRANCE_DOOR_NAME, CAMERA_OVERVIEW, CAMERA_ENTRANCE, CAMERA_GATE, "Sun_Daylight", "Sky_Fill",
    "Ground_Grass", "Road_Main", "Plaza_Front", "Garden_Flowerbed", "Garden_Circle_Plaza",
    "Bld_Plinth", "Canopy_Roof", "Gate_Pillar_L", "Gate_Pillar_R", "Reception_Counter",
)


# ----------------------------------------------------------------------
# Derived tables (walls and openings)
# ----------------------------------------------------------------------
def _build_walls():
    walls = {}
    for fl in ("G", "1"):
        ez, iz = EXT_WALL_Z[fl], INT_WALL_Z[fl]
        walls[f"{fl}_FRONT"] = dict(name=f"Wall_{fl}_Front", axis="X", fixed=EXT_CENTER_Y,
                                    a0=-BLD_OUT_X, a1=BLD_OUT_X, thick=EXT_WALL_T, z=ez, ext=True, floor=fl)
        walls[f"{fl}_BACK"] = dict(name=f"Wall_{fl}_Back", axis="X", fixed=-EXT_CENTER_Y,
                                   a0=-BLD_OUT_X, a1=BLD_OUT_X, thick=EXT_WALL_T, z=ez, ext=True, floor=fl)
        walls[f"{fl}_LEFT"] = dict(name=f"Wall_{fl}_Left", axis="Y", fixed=-EXT_CENTER_X,
                                   a0=-BLD_IN_Y, a1=BLD_IN_Y, thick=EXT_WALL_T, z=ez, ext=True, floor=fl)
        walls[f"{fl}_RIGHT"] = dict(name=f"Wall_{fl}_Right", axis="Y", fixed=EXT_CENTER_X,
                                    a0=-BLD_IN_Y, a1=BLD_IN_Y, thick=EXT_WALL_T, z=ez, ext=True, floor=fl)
        walls[f"{fl}_PART"] = dict(name=f"Wall_{fl}_Partition", axis="X", fixed=PARTITION_Y,
                                   a0=-BLD_IN_X, a1=BLD_IN_X, thick=INT_WALL_T, z=iz, ext=False, floor=fl)
        y0 = PARTITION_Y + INT_WALL_T / 2
        walls[f"{fl}_CLASS_L"] = dict(name=f"Wall_{fl}_Class_L", axis="Y", fixed=-CLASS_WALL_X,
                                      a0=y0, a1=BLD_IN_Y, thick=INT_WALL_T, z=iz, ext=False, floor=fl)
        walls[f"{fl}_CLASS_R"] = dict(name=f"Wall_{fl}_Class_R", axis="Y", fixed=CLASS_WALL_X,
                                      a0=y0, a1=BLD_IN_Y, thick=INT_WALL_T, z=iz, ext=False, floor=fl)
    return walls


def _build_openings():
    ops = []

    def window(oid, name, wall, fl, along, width=WINDOW_W, sill=WINDOW_SILL_H, height=WINDOW_H):
        z0 = FLOORS[fl] + sill
        ops.append(dict(id=oid, name=name, wall=wall, kind="WINDOW", floor=fl, along=along,
                        width=width, z0=z0, z1=z0 + height, frame_w=WINDOW_FRAME_W))

    for fl in ("G", "1"):
        for i, x in enumerate(WING_WINDOW_X):
            window(f"win_{fl}_front_r{i}", f"{fl}_Front_R{i}", f"{fl}_FRONT", fl, x)
            window(f"win_{fl}_front_l{i}", f"{fl}_Front_L{i}", f"{fl}_FRONT", fl, -x)
        for i, x in enumerate(BACK_WINDOW_X):
            window(f"win_{fl}_back_{i}", f"{fl}_Back_{i}", f"{fl}_BACK", fl, x)
        for i, y in enumerate(SIDE_WINDOW_Y):
            window(f"win_{fl}_left_{i}", f"{fl}_Left_{i}", f"{fl}_LEFT", fl, y)
            window(f"win_{fl}_right_{i}", f"{fl}_Right_{i}", f"{fl}_RIGHT", fl, y)

    # Large first-floor glazing flanking the balcony door
    for i, x in enumerate((-3.75, 3.75)):
        window(f"win_1_balcony_{i}", f"1_Balcony_{i}", "1_FRONT", "1", x, width=4.4, sill=0.95, height=2.65)

    def door(oid, name, wall, fl, along, hinge, swing):
        z0 = FLOORS[fl]
        ops.append(dict(id=oid, name=name, wall=wall, kind="DOOR", floor=fl, along=along,
                        width=DOOR_OPENING_W, z0=z0, z1=z0 + DOOR_OPENING_H, frame_w=DOOR_FRAME_W,
                        hinge=hinge, swing=swing, leaf_w=DOOR_LEAF_W, leaf_h=DOOR_LEAF_H,
                        leaf_t=DOOR_LEAF_T, door_name=f"Door_{name}"))

    for fl in ("G", "1"):
        door(f"door_{fl.lower()}_class_l", f"{fl}_Class_L", f"{fl}_CLASS_L", fl, 5.5, "lo", -1)
        door(f"door_{fl.lower()}_class_r", f"{fl}_Class_R", f"{fl}_CLASS_R", fl, 5.5, "lo", +1)
        door(f"door_{fl.lower()}_back_l", f"{fl}_Back_L", f"{fl}_PART", fl, -19.0, "lo", +1)
        door(f"door_{fl.lower()}_back_r", f"{fl}_Back_R", f"{fl}_PART", fl, 19.0, "hi", +1)
    door("door_1_balcony", "1_Balcony", "1_FRONT", "1", 0.0, "lo", -1)

    # Archways (no leaf)
    ops.append(dict(id="arch_g_lobby_back", name="G_Lobby_Back", wall="G_PART", kind="ARCH", floor="G",
                    along=0.0, width=2.4, z0=FLOOR_G_Z, z1=FLOOR_G_Z + 2.6, frame_w=ARCH_FRAME_W))
    ops.append(dict(id="arch_1_stair_landing", name="1_Stair_Landing", wall="1_PART", kind="ARCH", floor="1",
                    along=STAIR_X, width=STAIR_W, z0=FLOOR_1_Z, z1=FLOOR_1_Z + 2.5, frame_w=ARCH_FRAME_W))

    # Main entrance: two outward-swinging leaves
    ops.append(dict(id=ENTRANCE_DOOR_ID, name="Entrance", wall="G_FRONT", kind="ENTRANCE", floor="G",
                    along=ENTRANCE_X, width=ENTRANCE_OPENING_W, z0=PLINTH_TOP_Z,
                    z1=FLOOR_G_Z + ENTRANCE_OPENING_H, frame_w=ENTRANCE_FRAME_W,
                    swing=+1, leaf_w=ENTRANCE_LEAF_W, leaf_h=ENTRANCE_LEAF_H, leaf_t=ENTRANCE_LEAF_T))
    return ops


WALLS = _build_walls()
OPENINGS = _build_openings()
