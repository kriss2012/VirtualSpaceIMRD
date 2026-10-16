# Geometry Report – Phase 2

Blender 5.2.2 LTS. All dimensions are **approximations** (no verified IMRD drawings/photos); see `scripts/game_config.py`.

## Result
`tests/test_geometry.py`: **462/462 passed** (run against the saved `output/imrd_campus.blend`).

## Elevations (m, Z up; +Y = building front)
| Item | Value |
|---|---|
| Plinth top | 0.30 |
| Ground floor walking surface | 0.34 (4 cm tile on plinth) |
| First-floor walking surface | 4.30 (slab 0.30, underside 4.00) |
| Roof underside / top | 8.30 / 8.60, parapet to 9.60 |
| Exterior / interior wall thickness | 0.30 / 0.20 |

## Openings
Built with Exact Boolean difference on each wall, then dissolved coplanar tris and verified (0 non-manifold edges, positive volume) in the builder **and** in the test. 42 openings cut: 36 windows (2.4×1.5 m, sill 1.0 m above floor; two 4.4×2.65 m first-floor balcony windows), 9 doors (1.10×2.20 m opening), 2 arches, 1 entrance (3.6×2.6 m). Frames, lintels, sills and inset 4 cm glass are separate objects.
Test method: ray casts through each opening hit nothing; ray hits lintel, jamb and sill wall beside/above/below it.

## Doors (11 leaves, in `Gameplay_Objects`)
* Origin = hinge point. Closed rot Z = 0; open = ±90° (sign chosen so the leaf swings to the configured side), stored as custom props `imrd_door_id`, `imrd_hinge`, `imrd_open_rot_z_deg`, `imrd_state`.
* Leaf 0.96×2.10×0.045 (entrance leaves 1.70×2.45×0.05). Hinge is inset from the opening edge by frame + half leaf + 5 mm so the rotated leaf clears the jamb.
* Test: leaf fits clear width/height; hinge world position unchanged when rotated; a 4 cm point-sample of the leaf surface is never inside any wall, frame, glass, slab, stair or furniture mesh, in both closed and open poses.
* Collision for doors is not created yet (Phase 5, `Collision_Proxies` is empty).

## Staircase
22 risers × 0.18 m = 3.96 m (= 4.30 − 0.34); 21 treads × 0.28 m; width 1.8 m at X=5.0, running toward −Y from Y=7.30 to 1.42. Last riser rises exactly to the first-floor surface.
* Top landing: first-floor slab piece `Slab_Floor_1_Landing`, Y 0.10–1.42, continuing through a 1.8 m arch in the upper partition into the rear corridor zone. Bottom landing: ground floor Y 7.30–8.35 (not a separate object).
* Slab opening X 3.90–6.10, Y 1.42–7.50 (slab built from 4 pieces). Headroom over all treads ≥ 2.0 m (ray-tested). Handrails (0.9 m) both sides, guard rail at the open slab edge; no intersection with walls/frames (tested). Old defects (ends 0.3 m low, crossing wall, no opening) are fixed.

## Other fixes
Entrance canopy/balcony no longer overlaps the slab (coplanar), got a 1.0 m guard rail and a balcony door; sign moved to the parapet; canopy columns now reach the plaza; furniture heights derive from floor elevations (previously floating 0.1 m on the first floor); car wheels oriented; benches no longer float. Front wall no longer has an unfilled gap beside the entrance.

## Idempotency
Second in-session build: identical object names, collections, materials, light/camera counts, no leaked meshes, unrelated object preserved. Only `imrd_owner`-tagged objects are removed. `.blend` saves are preceded by a timestamped copy in `output/backups/`.

## Known issues / needed later changes
1. `02_player_controller.py` colliders/ground heights are stale: ground 0.32 vs 0.34, entrance gap is now ±1.8 (collider gap is ±3.5, so the player can walk through the wall at X 1.8–3.5), no stair/first-floor/interior support. (Phase 5.)
2. `run_game.py` toggles only `Interactive_Entrance_Door`; `Door_Entrance_B` (same `door_main` id) needs toggling too, and ±90° should come from `imrd_open_rot_z_deg`. Interactions registry has only the main door; other 9 doors have no interaction entries yet.
3. Compat edit made: `03_npc_interactions.py` now reuses the builder's `Interactive_Entrance_Door` if present (falls back to old slab).
4. Materials are still flat colours, no UVs, lighting unchanged (Phases 3–4). Legacy `tests/test_all_systems.py` still fails on its missing old PNG renders (expected until Phase 8).
5. Interiors beyond the two original classrooms are empty; the rear hall is an assumed common space.
6. Test limitation: point-in-solid sampling at 4 cm, not an analytic proof; the interactive game was not run.

## Commands
```powershell
$b = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
& $b --background --python scripts/01_build_campus.py -- --render      # build, save, previews
& $b --background output/imrd_campus.blend --python tests/test_geometry.py
& $b "output/imrd_campus.blend" --python "scripts/run_game.py"       # interactive
```
Previews: `output/geometry_preview_{overview,facade,plan_ground,plan_upper}.png` (Workbench renders).
