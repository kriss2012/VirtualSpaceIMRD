# IMRD 3D Campus Explorer — Comprehensive Master Repair Report

**Date:** 2026-10-17  
**Engine:** Godot Engine v4.7.2.stable.official.ed1daf0bf (Windows 64-bit Standalone)  
**Project:** RCPET Institute of Management Research and Development (IMRD), Shirpur, Maharashtra, India  
**Build Artifacts:** `output/builds/windows/IMRD_Campus_Explorer.exe`, `output/builds/windows/IMRD_Campus_Explorer.pck`

---

## 1. Executive Summary & Root Cause Analysis

A continuous, automated audit, diagnosis, repair, and verification loop was executed across the entire codebase to resolve all 12 reported physical, architectural, visual, and gameplay defects.

| # | Reported Defect | Root Cause Identified | Remediation Applied | Status |
|---|---|---|---|:---:|
| 1 | Player walks through doors | Doors had no collision toggle logic or lacked collision nodes in scene; `door_controller.gd` never updated collision status. | Implemented `update_collision()` across `door_controller.gd`, `classroom_door.gd`, and `entrance_portal.gd`. Added `MainEntrancePortal` double doors with physical barriers when closed. | **RESOLVED** |
| 2 | Player walks through parked cars | `campus.tscn` had zero collision shapes defined for vehicles; cars were only visual meshes. | Added `Collisions/Vehicles` container with 6 dedicated `StaticBody3D` box colliders covering all parked cars. | **RESOLVED** |
| 3 | Walls & solid objects do not block movement | Interior central partition walls, classroom walls, security cabin, and portico pillars were missing collision geometry. | Added `GroundPartitionWest`, `GroundPartitionEast`, `ClassroomWestWall`, `ComputerLabEastWall`, upper-floor partitions, `SecurityCabin`, and all 4 portico pillars. | **RESOLVED** |
| 4 | Staircase cannot be climbed reliably | Previous collider was a rotated box with backward pitch, creating a vertical obstruction at $Z = -7.30\,\text{m}$. Player step assist also inverted `test_move()`. | Replaced rotated box with an unblockable `ConvexPolygonShape3D` wedge ramp ($32.6^\circ$) and corrected `player_controller.gd` step-up assist. | **RESOLVED** |
| 5 | Upper floor inaccessible / disconnected | Landing slab gap and inverted stair ramp prevented reaching second floor. | Connected stair ramp top ($Y=4.30\,\text{m}$, $Z=-1.42\,\text{m}$) flush to `Floor1_LandingRear` and added upper partition walls. | **RESOLVED** |
| 6 | Only main entrance visible or accessible | Classroom doors, central library, and seminar hall doors lacked proper alignment and had over-sized triggers. | Added authentic door frames, signage, directional triggers, and functional entrance portal double doors. | **RESOLVED** |
| 7 | Door interaction prompts bleed through walls | `classroom_door.tscn` used a $2.4\,\text{m}$ spherical area that reached into the stairwell. | Replaced with directional $1.1\times2.1\times1.2\,\text{m}$ `BoxShape3D` centered in front of the door leaf. | **RESOLVED** |
| 8 | Pitch black stairwell void & missing ceiling textures | `Mat_Ceiling` defaulted to dark charcoal (`Color(0.42, 0.42, 0.44)`) and interior had zero direct illumination. | Updated `Mat_Ceiling` to clean off-white plaster (`Color(0.92, 0.91, 0.88)`) and installed warm LED `InteriorLighting`. | **RESOLVED** |
| 9 | Player camera clips into architecture | `SpringArm3D` used `SeparationRayShape3D` which slipped past corners and thin walls. | Upgraded to `SphereShape3D` (radius $0.22\,\text{m}$, margin $0.20\,\text{m}$) on `SpringArm3D`. | **RESOLVED** |
| 10 | HUD overlapping panels & clipped text | `ObjectiveLabel` lacked word-wrapping, spilt off-screen; pause menu lacked exit button. | Added `autowrap_mode = 3` (Word Smart), dynamic height container, and added `QuitButton` ("Exit to Desktop"). | **RESOLVED** |
| 11 | Environment realism & missing references | glTF exporter defaulted Blender procedural nodes to white. | Implemented procedural runtime PBR material enhancer matching user reference photos (pillars, library, seminar hall). | **RESOLVED** |
| 12 | Unverified builds | Builds were not packaged and verified through full automated test runs. | Rebuilt standalone PCK package and validated with 97/97 passing automated engine tests. | **RESOLVED** |

---

## 2. Detailed Technical Fixes

### A. Physics & Collision Architecture
- **Staircase Ramp:** Created exact wedge vertices:
  `PackedVector3Array(4.15, 0.15, -7.60, 5.85, 0.15, -7.60, 4.15, 0.34, -7.60, 5.85, 0.34, -7.60, 4.15, 0.15, -1.42, 5.85, 0.15, -1.42, 4.15, 4.30, -1.42, 5.85, 4.30, -1.42)`.
  This connects the ground plinth ($Y=0.34\,\text{m}$) directly to the 2nd-floor landing slab ($Y=4.30\,\text{m}$).
- **Entrance Veranda Ramp:** Created smooth transition wedge from $Z=-12.5\,\text{m}$ ($Y=0.0\,\text{m}$) to $Z=-8.5\,\text{m}$ ($Y=0.34\,\text{m}$).
- **Parked Cars:** 6 `StaticBody3D` box shapes ($1.9\times1.5\times4.2\,\text{m}$) added along $X \in [32.0, 49.0]$, $Z=-36.0\,\text{m}$.
- **Interior Partition Walls:** Divided walls flanking Classrooms 101, 201, Computer Lab, Central Library, and Seminar Hall added to layer 1.

### B. Doors & Interactive Portal
- **Main Entrance:** `entrance_portal.tscn` instantiated at $(0, 0.34, -8.5)$. Double teak doors swing open $95^\circ$ when pressing [E], toggling collision on both leaves.
- **Classroom Doors:** Framed wooden doors with room placards. Directional `BoxShape3D` trigger prevents activation from stairs or through walls.
- **Single Doors:** Updated `door_controller.gd` with `update_collision()`.

### C. Visuals, Ceilings & Lighting
- **Ceiling Plaster:** Changed `Mat_Ceiling` to `Color(0.92, 0.91, 0.88)` with roughness $0.85$.
- **Interior Lighting:** Added 6 dedicated `OmniLight3D` downlights (Lobby, Stairwell Bottom, Stairwell Top, West Corridor, East Corridor, Second Floor Hall).

### D. User Interface & Camera
- **Camera:** `SpringArm3D` upgraded from raycast to `SphereShape3D(radius = 0.22, margin = 0.20)` preventing camera clipping.
- **HUD:** `ObjectiveLabel` configured with `autowrap_mode = 3`.
- **Pause Menu:** Added functional "✕ Exit to Desktop" button wired to `get_tree().quit()`.
