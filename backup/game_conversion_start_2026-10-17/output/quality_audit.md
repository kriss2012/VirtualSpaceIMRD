# IMRD Campus – Quality Audit (Phase 1)

Date: 2026-10-16. Blender: **5.2.2 LTS** (`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`).
Backup: `backup/pre_upgrade_2026-10-16/` (scripts, tests, README).

## Status of files
| Item | State |
|---|---|
| scripts 01–05, run_game, tests | Present. 01, 02 read in full. 03, 04, 05, run_game, tests only skimmed (symbols); not yet verified. |
| `output/imrd_campus.blend` | **Missing.** `output/` was empty/absent; the README's renders and blend don't exist. Previous "passed" claims are unverified. |
| Reference photos / drawings | None in project. Architecture is an **approximation**, not verified IMRD dimensions. |
| Git repo | None; the backup folder is the only safety net. |

## Findings (verified from source)
**Coordinates:** meters, Z up. Building X[-20.6,20.6] Y[-8.6,8.6]; front is +Y; gate at Y=75; player spawn (0,68,0). Floors: plinth top ≈0.32, first-floor slab top ≈4.30, roof ≈8.6.

**Build script (01):**
- Calls `read_factory_settings(use_empty=True)` – destructive, not idempotent; rebuilds everything and renders at build time.
- All geometry is box/cylinder primitives; no bevels, no window/door openings (windows are glass slabs on solid walls; entrance door is a slab, not a hinged door).
- Materials: flat Principled colors only; no procedural detail, no UVs worked on; `create_material` doesn't set `use_nodes`(works in 5.x, but fragile). Glass is opaque-ish (metallic 0.2, no transmission/alpha).
- Lighting: two sun lights, no World setup, no color-management settings, no render engine set.
- Stairs: 16 steps × 0.23 = rises to ≈4.0 m, ends below slab top 4.30; no opening in the first-floor slab, stairs run toward -Y into the corridor wall region (y 2.0 → -3.4) crossing `Wall_Int_Corridor_G` at y=0.
- Interior partition walls have no door openings → classrooms are unreachable.
- First-floor furniture exists but the first floor is unreachable.
- Canopy roof at z=4.15 overlaps the slab; columns at Y=12 vs canopy Y 8.5–12.5 (OK) but sign panel z-overlaps canopy.
- Car wheels share the name pattern `Car_i_Wheel` (auto-suffixed, unstable names). Trees are identical stacked cylinders.
- 5 cameras requested; only 2 exist (overview, entrance). Collections lack Collision, NPCs, Gameplay, Cameras separation.

**Player (02):**
- Collision: hand-written AABB list (11 boxes); no interior walls, furniture, doors or stairs. Check is point-vs-expanded-box with no swept test → tunneling at sprint with dt up to 0.08 (0.8 m/frame at 10.8 m/s) is mostly OK vs 0.4 m walls only because of radius 0.45, but marginal.
- Move rejected entirely on collision (no sliding) → sticks on walls. Collision test uses `pz+1.6`, so it blocks wrongly vs. height checks.
- Ground height: hardcoded 0.32 inside the building footprint, 0.15 steps patch; **no stair/first-floor support**, so first floor is unreachable. Furniture/lobby counters don't block.
- No fall/respawn boundary; no jump-input buffering; key state held in class-level dict shared across instances; keys not cleared on stop/focus loss.
- Timer uses `time.time()` with variable step, dt clamp 0.08; no fixed timestep. Movement is otherwise frame-independent. Diagonals normalized ✔.
- No camera obstruction handling. Camera lerp factor is per-frame (frame-rate dependent).
- Q exits (conflicts with potential key binding but matches spec).

**Not yet audited:** NPC distances/IDs, mission reward-once logic, save/restore, HUD handler cleanup, run_game panel, test contents. Phase 6/7 will verify these before changes.

## Test coverage (from symbols)
`test_script_syntax, test_missions_logic, test_collision_math, test_rendered_outputs, test_blend_file`. No scene, gameplay-physics, door, collectible, save/restore, or handler-cleanup tests.

## Implementation plan
1. **P2 Geometry:** shared `imrd_config.py` (scale, floors, quality); make 01 idempotent (no factory reset when run in an existing file; clear only own collections); wall openings (booleans avoided → build walls from segments around doors/windows), classroom doors, proper stair run with slab opening, hinged doors with pivots, bevels on trims, instanced desks/lamps/trees with varied shape.
2. **P3 Materials:** `materials.py` with reusable procedural PBR builders (plaster, concrete, asphalt, tile, wood, glass w/ transmission, foliage…).
3. **P4 Lighting:** World sky, color management (AgX), Eevee gameplay preset vs. Cycles/Eevee render preset, 5 cameras.
4. **P5 Physics:** collision proxies in a `Collision` collection (AABB + height-field for stairs/floors), swept per-axis movement with sliding, fixed 1/60 s step, respawn, camera obstruction.
5. **P6–7:** data-driven interactions, reward-once checks, save/restore, HUD handler cleanup.
6. **P8–9:** expanded tests, real renders (low-res iteration, final at end), reports, README.

## Constraints to document
Blender-only prototype; no standalone executable. Interactive controller/HUD can only be validated in the Blender UI, not headless.
