# IMRD 3D Campus Explorer — Automated Engine Test Report

**Execution Date:** 2026-10-17  
**Runtime Binary:** `output/builds/windows/IMRD_Campus_Explorer_console.exe`  
**Main Package Tested:** `output/builds/windows/IMRD_Campus_Explorer.pck`  
**Engine Version:** Godot Engine v4.7.2.stable.official.ed1daf0bf  
**Execution Command:**  
`output\builds\windows\IMRD_Campus_Explorer_console.exe --headless --main-pack output\builds\windows\IMRD_Campus_Explorer.pck res://scenes/test_runner.tscn`

---

## Test Results Overview

- **Total Test Groups:** 10
- **Total Assertions Executed:** 97
- **Passed:** 97
- **Failed:** 0
- **Overall Status:** **100% PASS**

---

## Detailed Test Group Breakdown

### Group 1: Autoload Singletons (3/3)
- [PASS] GameManager singleton loaded
- [PASS] MissionManager singleton loaded
- [PASS] SaveManager singleton loaded

### Group 2: Main Menu Scene (5/5)
- [PASS] Main menu scene resource exists
- [PASS] Main menu instantiated successfully
- [PASS] Start button found
- [PASS] Controls button found
- [PASS] Quit button found

### Group 3: Campus 3D World Scene & Collisions (34/34)
- [PASS] Campus scene resource exists
- [PASS] Campus 3D world instantiated
- [PASS] WorldEnvironment node active
- [PASS] DirectionalLight3D (Sun) active
- [PASS] VisualEnvironment container present
- [PASS] campus_terrain GLB instantiated
- [PASS] campus_architecture GLB instantiated
- [PASS] campus_props GLB instantiated
- [PASS] campus_furniture GLB instantiated
- [PASS] campus_vegetation GLB instantiated
- [PASS] Collisions root present
- [PASS] Ground static collision present
- [PASS] Entrance steps smooth ramp present
- [PASS] Entrance ramp uses smooth ConvexPolygonShape3D
- [PASS] Plinth static collision present
- [PASS] Stairs ramp collision present
- [PASS] Stairs ramp uses smooth ConvexPolygonShape3D
- [PASS] Interior lighting system present
- [PASS] Second floor West slab collision present
- [PASS] Second floor East slab collision present
- [PASS] Second floor Landing collision present
- [PASS] Authentic IMRD entrance portico present
- [PASS] Authentic IMRD Library section present
- [PASS] Authentic IMRD Seminar Hall present
- [PASS] Vehicles collision container present
- [PASS] All 6 parked cars have active static body collisions
- [PASS] Ground partition wall collision present
- [PASS] Classroom 101 wall collision present
- [PASS] Computer Lab wall collision present
- [PASS] Security cabin collision present
- [PASS] Doors root present
- [PASS] Main Entrance animated portal present
- [PASS] Classroom 101 door present
- [PASS] Computer Lab door present
- [PASS] Central Library door present
- [PASS] Second floor Classroom 201 door present
- [PASS] Second floor Seminar Hall door present

### Group 4: Player Controller & Camera (7/7)
- [PASS] Player scene resource exists
- [PASS] Player is CharacterBody3D
- [PASS] Player has physics collision shape
- [PASS] Player has CameraPivot
- [PASS] Player has SpringArm3D for obstruction avoidance
- [PASS] SpringArm3D uses SphereShape3D preventing wall/corner clipping
- [PASS] Player has 3rd-person Camera3D
- [PASS] Player initializes to spawn Z = -68.0

### Group 5: Doors & Hinge Pivot Interaction (16/16)
- [PASS] Classroom door scene resource exists
- [PASS] Classroom door uses targeted BoxShape3D interaction area
- [PASS] Classroom door starts closed
- [PASS] Classroom door state transitions to OPEN after interaction
- [PASS] Classroom door state transitions back to CLOSED
- [PASS] Entrance portal scene resource exists
- [PASS] Entrance portal has interact method
- [PASS] Entrance double doors start closed
- [PASS] Entrance double doors transition to OPEN after interaction
- [PASS] Portal prompt updates to Close
- [PASS] Entrance double doors transition back to CLOSED
- [PASS] Standard single door scene exists
- [PASS] Single door has interact method
- [PASS] Single door starts closed
- [PASS] DoorBody collision active when closed
- [PASS] Single door opened
- [PASS] DoorBody collision disabled when open for passage

### Group 6: NPC Prof. Sharma & Mission 1 (3/3)
- [PASS] NPC scene resource exists
- [PASS] NPC is Prof. Sharma
- [PASS] First Day mission completed after talking to guide
- [PASS] XP rewarded for completing First Day mission

### Group 7: Collectible Student ID Card & Mission 2 (3/3)
- [PASS] ID card scene resource exists
- [PASS] Card has interact method
- [PASS] Lost ID Card mission completed on pickup
- [PASS] Student_ID_Card added to inventory

### Group 8: Campus Explorer Locations & Mission 3 (5/5)
- [PASS] Visited classroom recorded
- [PASS] Visited lobby recorded
- [PASS] Visited courtyard recorded
- [PASS] Campus Explorer mission completed after all 3 areas visited

### Group 9: Save & Load Persistence (6/6)
- [PASS] Game saved to user://imrd_game_save.json successfully
- [PASS] Game save loaded back successfully
- [PASS] Saved XP restored correctly
- [PASS] Saved Level restored correctly
- [PASS] Saved mission state preserved

### Group 10: Stair Climb & Second Floor Traversal (10/10)
- [PASS] Campus scene loads for traversal test
- [PASS] Player found in campus
- [PASS] Player starts at ground plinth Y >= 0.34
- [PASS] Stairs ramp collision node exists
- [PASS] Stairs ramp shape is ConvexPolygonShape3D
- [PASS] Stairs ramp has 3D convex hull points
- [PASS] Stair ramp connects seamlessly to ground plinth (Y=0.34 at Z=-7.6)
- [PASS] Stair ramp connects seamlessly to second floor landing (Y=4.30 at Z=-1.42)
- [PASS] Classroom 201 door accessible on second floor (Y >= 4.0)
- [PASS] Seminar Hall door accessible on second floor (Y >= 4.0)

---
*Report automatically generated following verification of the compiled standalone package.*
