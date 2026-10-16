"""
export_campus_glb.py
====================
Automated glTF/GLB Asset Pipeline for IMRD Campus Game.
Exports modular, game-ready 3D assets from Blender into Godot:
1. campus_architecture.glb
2. campus_terrain.glb
3. campus_props.glb
4. campus_furniture.glb
5. campus_vegetation.glb
6. campus_doors.glb
7. character_student.glb
8. npc_guide.glb
9. campus_full.glb (consolidated reference)
"""

import sys
import bpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLEND_FILE = ROOT / "output" / "imrd_campus.blend"
ASSETS_MODELS = ROOT / "assets" / "models"
GAME_MODELS = ROOT / "game" / "assets" / "models"

ASSETS_MODELS.mkdir(parents=True, exist_ok=True)
GAME_MODELS.mkdir(parents=True, exist_ok=True)


def export_selection(target_path, objects):
    """Select specific objects and export as GLB."""
    bpy.ops.object.select_all(action='DESELECT')
    valid_count = 0
    for obj in objects:
        if obj and obj.name in bpy.data.objects:
            obj.select_set(True)
            valid_count += 1
    if valid_count == 0:
        print(f"[GLB Exporter] Warning: No objects selected for {target_path.name}")
        return False

    # Perform GLTF / GLB export
    bpy.ops.export_scene.gltf(
        filepath=str(target_path),
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_materials='EXPORT',
        export_cameras=False,
        export_lights=False,
        export_extras=True,
        export_yup=True,
    )
    # Also copy to game assets
    game_path = GAME_MODELS / target_path.name
    import shutil
    shutil.copy2(target_path, game_path)

    size_kb = target_path.stat().st_size / 1024
    print(f"[GLB Exporter] Exported {target_path.name}: {valid_count} objects ({size_kb:.1f} KB)")
    return True


def run_export():
    if not BLEND_FILE.exists():
        print(f"[GLB Exporter] ERROR: {BLEND_FILE} does not exist!")
        sys.exit(1)

    print(f"[GLB Exporter] Opening {BLEND_FILE}...")
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_FILE))

    # 1. Campus Architecture (Main building, slabs, walls, roof, plinth, stairs, rails)
    arch_objs = []
    for cname in ["Building_Structure", "Interior_Architecture"]:
        col = bpy.data.collections.get(cname)
        if col:
            for o in col.objects:
                if not o.name.startswith("Door_") and not o.name.startswith("Interactive_"):
                    arch_objs.append(o)
    export_selection(ASSETS_MODELS / "campus_architecture.glb", arch_objs)

    # 2. Campus Terrain (Roads, curbs, paving, lawn, plaza, flowerbed)
    terrain_objs = []
    col = bpy.data.collections.get("Terrain_Roads")
    if col:
        terrain_objs.extend(col.objects)
    export_selection(ASSETS_MODELS / "campus_terrain.glb", terrain_objs)

    # 3. Props & Vehicles & Gate
    props_objs = []
    for cname in ["Props_Vehicles", "Gate_Boundary"]:
        col = bpy.data.collections.get(cname)
        if col:
            props_objs.extend(col.objects)
    export_selection(ASSETS_MODELS / "campus_props.glb", props_objs)

    # 4. Interior Furniture
    furn_objs = []
    col = bpy.data.collections.get("Interior_Furniture")
    if col:
        furn_objs.extend(col.objects)
    export_selection(ASSETS_MODELS / "campus_furniture.glb", furn_objs)

    # 5. Vegetation (Trees, organic crowns, shrubs)
    veg_objs = []
    col = bpy.data.collections.get("Vegetation")
    if col:
        veg_objs.extend(col.objects)
    export_selection(ASSETS_MODELS / "campus_vegetation.glb", veg_objs)

    # 6. Interactive Doors (Each door leaf)
    door_objs = []
    for o in bpy.data.objects:
        if o.name.startswith("Door_") or o.name.startswith("Interactive_Entrance_Door"):
            door_objs.append(o)
    export_selection(ASSETS_MODELS / "campus_doors.glb", door_objs)

    # 7. Player Student Character
    player_objs = []
    col = bpy.data.collections.get("Player_Student")
    if col:
        player_objs.extend(col.objects)
    if not player_objs:
        player_objs = [o for o in bpy.data.objects if o.name.startswith("Player_")]
    export_selection(ASSETS_MODELS / "character_student.glb", player_objs)

    # 8. NPCs and Interactives (Prof. Sharma, collectible card)
    npc_objs = []
    col = bpy.data.collections.get("NPCs_and_Interactives")
    if col:
        npc_objs.extend(col.objects)
    if not npc_objs:
        npc_objs = [o for o in bpy.data.objects if o.name.startswith("NPC_") or o.name.startswith("Item_")]
    export_selection(ASSETS_MODELS / "npc_guide.glb", npc_objs)

    # 9. Full Campus Environment (Consolidated scene excluding cameras, lights, player)
    full_objs = arch_objs + terrain_objs + props_objs + furn_objs + veg_objs + door_objs + npc_objs
    export_selection(ASSETS_MODELS / "campus_full.glb", full_objs)

    print("\n[GLB Exporter] All 9 modular GLB assets exported and synchronized to game/assets/models/ successfully!")


if __name__ == "__main__":
    run_export()
