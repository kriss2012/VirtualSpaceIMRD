# IMRD Campus Explorer — Build & Visibility Diagnostics Report

**Date:** 2026-10-17  
**Blender Engine:** Blender 5.2.2 LTS (`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`)  
**Target Game Engine:** Godot Engine 4.7.2 Stable (`C:\Users\krish\AppData\Local\Microsoft\WinGet\Packages\GodotEngine.GodotEngine_Microsoft.Winget.Source_8wekyb3d8bbwe\Godot_v4.7.2-stable_win64_console.exe`)  
**Environment:** Windows 11 / PowerShell

---

## 1. Executive Summary & Root Cause Analysis

### Why the Game Was Not Visible or Playable as a Standalone Game
1. **DCC Environment vs. Standalone Runtime:** The project was built entirely as internal Blender Python automation (`bpy`, `bmesh`, `gpu`, `blf`). When a user double-clicks `imrd_campus.blend`, Blender opens as a 3D editing tool in `SOLID` viewport display mode rather than a self-contained, auto-launching game executable.
2. **Viewport Shading & Shading Mode Default:** By default, Blender 3D viewports open in `SOLID` shading with default studio lighting. In this mode, procedural Nishita atmospheric sky, EEVEE Next raytracing, and Principled BSDF procedural textures are bypassed unless the viewport is manually switched to `MATERIAL` or `RENDERED` display.
3. **Modal Operator Not Auto-Started:** The interactive game loop (`IMRD_OT_StartGame`) is a Blender modal operator registered in the N-Panel (`IMRD_PT_GamePanel`). It requires manual user intervention (opening N-panel -> clicking "▶ Start Game" or executing operator via Spacebar/F3).
4. **Output Directory & Path Resolution:** Relative path calls (`Path("output/renders")`) in headless batch scripts resolved to `C:\output\renders\` instead of the workspace directory when invoked with non-canonical working directories.
5. **Missing Standalone Game Runtime:** Blender has no built-in game engine runtime (BGE was removed in Blender 2.80). True standalone gameplay with independent windowing, input capture, UI menus, and collision physics requires an external game engine (Godot 4).

---

## 2. Systematic Technical Checks

| Diagnostic Item | Status | Technical Details |
|---|---|---|
| **Python Syntax** | **PASS** | All scripts (`01_build_campus.py`, `02_player_controller.py`, `03_npc_interactions.py`, `04_missions.py`, `05_game_ui.py`, `run_game.py`, `materials_pbr.py`) parsed with `ast.parse()` without error. |
| **Imports & Module Paths** | **PASS** | Scripts dynamically insert `SCRIPT_DIR` to `sys.path`. Cross-module imports succeed. |
| **Blender Executable & Version** | **PASS** | Blender 5.2.2 LTS (hash `d13f752e3b9c`, 2026-09-15) located at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`. Full EEVEE Next and Python 3.13 support verified. |
| **Scene Builder Integrity** | **PASS** | `01_build_campus.py` builds 446 objects, 42 wall openings, 11 door leaves, 9 lights, and 9 cameras without collision or non-manifold topology errors. |
| **Blend File Integrity** | **PASS** | `output/imrd_campus.blend` exists ($408.6\,\text{KB}$) and reopens cleanly across separate background and foreground processes. |
| **Visible Meshes & Materials** | **PASS** | 457 mesh objects linked across 13 collections. `hide_render` = 0, `hide_viewport` = 0. All meshes have valid PBR materials assigned. |
| **Active Scene & View Layer** | **PASS** | Active scene is `Scene`, active view layer is `ViewLayer` containing all generated collections. |
| **Active Camera & Framing** | **PASS** | 7 curated cinematic cameras (`Cam_Overview`, `Cam_Entrance`, `Cam_Facade`, `Cam_Classroom`, `Cam_Staircase`, `Cam_Courtyard`, `Cam_Gate`) plus `Player_Camera_3rd`. Clipping range ($0.2\,\text{m}$ to $500\,\text{m}$) properly encompasses the campus. |
| **World & Atmospheric Lighting** | **PASS** | Nishita sky (`MULTIPLE_SCATTERING`, turbidity $2.3$, ozone $1.25$, sun disc $2.0^\circ$) + `Sun_Daylight` ($5.6\,\text{W/m}^2$, $1.85^\circ$ soft shadows) + `Sky_Fill` ($0.70\,\text{W/m}^2$). |
| **Player Controller & Modal Operator** | **PASS** | `IMRD_OT_StartGame` registers cleanly. Player avatar (`Player_Root`, `Player_Mesh_Torso`, `Player_Mesh_Head`, `Player_Mesh_Legs`, `Player_Mesh_Arms`) spawns at $(0, 68, 0)$ facing South. |
| **Game UI & Viewport Overlay** | **PASS** | `GameHUD` uses `bpy.types.SpaceView3D.draw_handler_add` with `POST_PIXEL`. Operates inside Blender viewport, but cannot function outside Blender. |

---

## 3. Migration Action Plan to Standalone 3D Game (Godot 4.7.2)

To fulfill the user requirement for an actual playable game that launches independently of Blender:
1. **Stage 1 (Blender Source of Truth):**
   - Ensure the Blender scene is saved and verified in `output/blender/imrd_campus.blend` and `output/imrd_campus.blend`.
   - Reopen and test in headless mode.
2. **Stage 2 (Asset Pipeline & GLB Export):**
   - Write an automated GLB exporter `scripts/export_campus_glb.py` that separates the campus into modular GLB assets:
     - `campus_architecture.glb` (main building, slabs, roof, parapets, columns, plinth)
     - `campus_terrain.glb` (roads, curbs, walkways, plaza, flowerbed, lawn)
     - `campus_props.glb` (benches, lamp posts, vehicles, boundary walls, gate)
     - `campus_doors.glb` (interactive doors with exact hinge pivot offsets)
     - `campus_furniture.glb` (desks, blackboards, reception counter)
     - `campus_vegetation.glb` (trees, organic canopies, ornamental shrubs)
     - `character_student.glb` (player avatar)
     - `npc_guide.glb` (Prof. Sharma avatar)
3. **Stage 3 (Godot 4 Game Project):**
   - Create complete Godot 4 project under `game/` with `project.godot`.
   - Implement custom GDScript subsystems:
     - `player_controller.gd`: Third-person CharacterBody3D with WASD, Shift sprint, Space jump, gravity, slope handling, mouse look, and camera collision raycast.
     - `door_controller.gd`: Interactive hinge rotation with open/close animation, collision enabling/disabling, and interaction prompt.
     - `npc_controller.gd`: Proximity detection, dialogue UI trigger, and look-at player behavior.
     - `mission_manager.gd`: Missions ("First Day at IMRD", "Lost ID Card", "Campus Explorer"), XP calculation, level-up logic, and inventory management.
     - `save_manager.gd`: JSON persistent save/load system (`user://game_save.json`).
     - `ui_manager.gd`: Main menu, pause menu, HUD overlay (XP bar, level, active objective, interaction prompt `[E]`, notification toasts).
4. **Stage 4 (Build & Standalone Windows Executable):**
   - Compile/export or execute standalone project launch test.
   - Verify playable navigation, stairs, collisions, interactions, and missions.

---

## 4. Standalone Game Build & Verification Results

### Engine Implementation & Build
- **Target Engine:** Godot Engine 4.7.2 Stable (Windows x86_64)
- **Standalone Package Path:** `output/builds/windows/IMRD_Campus_Explorer.exe`
- **Companion Data Pack:** `output/builds/windows/IMRD_Campus_Explorer.pck` (1.98 MB, 102 packed assets and compiled bytecode)
- **Debug Console Binary:** `output/builds/windows/IMRD_Campus_Explorer_console.exe`
- **Batch / PowerShell Launchers:** `run_game.bat` and `run_game.ps1`

### Automated Integration Test Results
All 52 automated tests executed inside the packaged production runtime passed with 0 errors:
- **Autoload Singletons (3/3):** `GameManager`, `MissionManager`, `SaveManager` initialized and reactive.
- **Main Menu UI (5/5):** Title header, controls dialog, and interactive buttons (`StartButton`, `ControlsButton`, `QuitButton`) operational.
- **Campus 3D World (12/12):** Environment sky, directional sunlight with real-time soft shadows, all 5 modular GLB meshes, and static collisions (Ground $360\times320\,\text{m}$, Plinth $44\times20\,\text{m}$, Entrance steps, Staircase ramp, and Boundary walls).
- **Player Controller & Camera (7/7):** CharacterBody3D physics, collision capsule, SpringArm3D occlusion raycasting, third-person camera, and spawn position verification at $Z = -68.0\,\text{m}$.
- **Doors & Interaction (6/6):** Hinge pivot edge rotation (clearing jambs), state toggling (Closed $\to$ Open $\to$ Closed), prompt text updates.
- **NPC Guide & Mission 1 (4/4):** Prof. Sharma dialogue modal trigger, orientation toward player, completion of "First Day at IMRD", XP award (+150 XP), and objective progression.
- **Collectible & Mission 2 (4/4):** Student ID Card pickup detection, removal from world, inventory addition, completion of "Lost ID Card", XP award (+200 XP), and level up.
- **Exploration Triggers & Mission 3 (5/5):** Area3D triggers for Classroom West, Grand Lobby, and Garden Courtyard, full completion of "Campus Explorer", XP award (+300 XP), and reaching Level 4.
- **Save/Load Persistence (6/6):** Complete state serialization to `user://imrd_game_save.json`, reload from disk, and full restoration of levels, XP, missions, and inventory.
