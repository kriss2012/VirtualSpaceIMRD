# RCPET IMRD Shirpur — 3D Campus Explorer Game

A complete, playable 3D campus exploration game representing **R. C. Patel Educational Trust's Institute of Management Research and Development (IMRD), Shirpur, Maharashtra, India**.

Built with an automated **Blender 5.2.2 LTS $\to$ glTF $\to$ Godot Engine 4.7.2** asset and gameplay pipeline.

---

## 🚀 Quick Start: Play Standalone Game (No Blender Required)

### Launch Options
1. **Direct Double-Click:** Run `run_game.bat` in the project root.
2. **From PowerShell:**
   ```powershell
   .\run_game.ps1
   ```
3. **Launch Executable Directly:**
   ```powershell
   & "output\builds\windows\IMRD_Campus_Explorer.exe"
   ```
4. **Debug Console Mode (Live engine logs & prints):**
   ```powershell
   .\run_game.ps1 -Console
   ```

---

## 🎮 Controls & Gameplay Mechanics

| Key / Input | Action | Description |
|---|---|---|
| **W, A, S, D** or **Arrow Keys** | **Move** | Third-person omnidirectional player movement |
| **Mouse Move** | **Look / Camera Orbit** | Smooth 3D mouse look with pitch clamping ($-65^\circ$ to $+60^\circ$) |
| **Left Shift** (Hold) | **Sprint** | Increases running velocity from $6.0\,\text{m/s}$ to $10.5\,\text{m/s}$ |
| **Spacebar** | **Jump** | Vertical impulse with gravity ($18.0\,\text{m/s}^2$) and grounded detection |
| **E** | **Interact** | Multi-purpose interaction key: talk to NPCs, pick up items, open/close doors |
| **Escape** or **Q** | **Pause / Menu** | Toggles pause menu, releases/captures mouse cursor |

---

## 🏛️ Campus Features & Missions

### 1. Campus World & Environments
- **Approach Avenue & Main Gate:** Boundary walls, security pillars, overhead arch beam with RCPET IMRD signage, streetlamps, and landscaped road dividers.
- **Main Academic Building:** Reinforced plinth ($0.32\,\text{m}$ elevation), grand entrance portico canopy, exterior facade louvers, curtain glass walls, and floor slabs.
- **Interior Layout:** Ground Floor Reception Foyer, Grand Lobby, Classroom West, Computer Lab, and Academic Library.
- **Grand Central Staircase:** Traverses from Ground Floor ($Z = 0.32\,\text{m}$) to First Floor ($Z = 4.30\,\text{m}$) with slope-assisted character physics.
- **Garden Courtyard:** Circular paved plaza, concentric ornamental flowerbeds, and seating rings.

### 2. Interactive Systems & Missions
- **Mission 1: First Day at IMRD**
  - Meet **Prof. Sharma (Campus Guide)** at the entrance walkway.
  - Press `[E]` to trigger interactive dialogue and receive orientation guidelines (+150 XP).
- **Mission 2: Lost ID Card**
  - Spot the dropped **Student ID Card** near the entrance walkway zebra crossing.
  - Press `[E]` to pick it up, adding it to your inventory and gaining +200 XP (Level Up!).
- **Mission 3: Campus Explorer**
  - Walk into **Classroom West**, **Grand Lobby**, and the **Garden Courtyard**.
  - Area triggers detect your presence, completing exploration objectives and unlocking +300 XP.
- **Interactive Doors:**
  - Hinged entrance and classroom doors rotate smoothly around their edge hinge axis ($90^\circ$) with dynamic collision updates.

### 3. Persistent Save / Load
- Game automatically saves upon completing missions, collecting items, and leveling up.
- Stored as versioned JSON in `user://imrd_game_save.json`.
- Restores XP, level, inventory items, and completed objectives across game sessions.

---

## 📁 Repository Layout

```
IMRD-Blender-Game/
├── run_game.bat                   # Double-click launcher for Windows
├── run_game.ps1                   # PowerShell game launcher
├── README.md                      # Complete documentation and instructions
│
├── game/                          # Godot Engine 4.7.2 Game Project
│   ├── project.godot              # Godot project settings, inputs, autoloads
│   ├── export_presets.cfg         # Windows Desktop export configuration
│   ├── scenes/
│   │   ├── main_menu.tscn         # Main menu with start, controls, quit
│   │   ├── campus.tscn            # Master 3D world with lighting, collisions & GLBs
│   │   ├── player.tscn            # Third-person student avatar CharacterBody3D
│   │   ├── npc.tscn               # Prof. Sharma guide CharacterBody3D
│   │   ├── door.tscn              # Interactive hinged door with Area3D
│   │   ├── item_id_card.tscn      # Collectible ID card with hover animation
│   │   ├── test_runner.tscn       # Automated engine test harness scene
│   │   └── ui.tscn                # HUD overlay (XP, objectives, toasts, dialogue)
│   ├── scripts/
│   │   ├── game_manager.gd        # State machine, pause, mouse capture
│   │   ├── mission_manager.gd     # Missions, XP, leveling, inventory
│   │   ├── save_manager.gd        # JSON persistence system
│   │   ├── player_controller.gd   # Physics movement, sprint, jump, camera
│   │   ├── door_controller.gd     # Hinge rotation and collision toggle
│   │   ├── npc_controller.gd      # Dialogue trigger and look-at logic
│   │   ├── item_id_card.gd        # Hover animation and pickup
│   │   ├── location_trigger.gd    # Area3D exploration detector
│   │   ├── ui_manager.gd          # HUD and dialogue UI controller
│   │   └── main_menu.gd           # Menu button actions
│   └── assets/models/             # 9 imported, game-ready GLB assets
│
├── output/
│   ├── builds/windows/            # Standalone Windows Game Build
│   │   ├── IMRD_Campus_Explorer.exe         # Standalone desktop executable
│   │   ├── IMRD_Campus_Explorer.pck         # Packed assets & bytecode (1.98 MB)
│   │   └── IMRD_Campus_Explorer_console.exe # Debug console executable
│   ├── imrd_campus.blend          # Master Blender 5.2.2 LTS 3D project
│   ├── build_diagnostics.md       # Full technical diagnostics & audit report
│   └── renders/                   # 7 validated PBR camera renders
│
├── scripts/                       # Blender Pipeline Scripts
│   ├── 01_build_campus.py         # Procedural 3D campus builder in Blender
│   ├── export_campus_glb.py       # Modular GLB export pipeline
│   ├── materials_pbr.py           # Physically based materials & Nishita sky
│   └── game_config.py             # Single source of truth for campus geometry
│
└── tests/
    └── test_all_systems.py        # Blender system test suite (5/5 passed)
```

---

## 🧪 Automated Testing

### 1. Godot Game Engine Test Suite (52/52 Tests Passed)
To run the automated engine integration tests headless:
```powershell
& "C:\Users\krish\AppData\Local\Microsoft\WinGet\Packages\GodotEngine.GodotEngine_Microsoft.Winget.Source_8wekyb3d8bbwe\Godot_v4.7.2-stable_win64_console.exe" --headless --path game res://scenes/test_runner.tscn
```

### 2. Standalone Package Production Test (52/52 Tests Passed)
To run the test suite directly against the compiled Windows `.pck` build:
```powershell
& "output\builds\windows\IMRD_Campus_Explorer_console.exe" --headless --main-pack "output\builds\windows\IMRD_Campus_Explorer.pck" res://scenes/test_runner.tscn
```

### 3. Blender Environment Tests (5/5 Tests Passed)
To validate the master Blender scene and geometry:
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background output\imrd_campus.blend --python tests/test_all_systems.py
```
