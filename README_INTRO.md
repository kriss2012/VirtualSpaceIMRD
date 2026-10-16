# IMRD Cinematic Intro - run instructions

Adds a ~17 s opening cinematic + main menu in front of the existing game.
Runtime: **Blender 5.x interactive 3D viewport** (the project has not migrated to Godot, so nothing is built for Godot).

## Files

| File | What |
|------|------|
| `scripts/06_intro_cinematic.py` | **New.** Camera path, title, menu, skip, hand-off, preview render, self-test |
| `scripts/run_game.py` | 4 small marked edits `[INTRO INTEGRATION n/4]` (optional import, `_running` guard on `imrd.start_game`, register, autostart) |
| `scripts/tests/test_intro_logic.py` | Plain-Python tests (no Blender needed) |
| `output/intro_config.json` | Generated shot list / timing |
| `output/intro_report.md` | Generated test report (only states what was actually run) |
| `output/intro_preview/` | Preview render output (created by `--render-preview`) |

Copy `06_intro_cinematic.py`, the edited `run_game.py` and `tests/` into your `scripts/` folder. Nothing else changes; `01`-`05` are untouched.

## Play it (interactive)

```
blender output/imrd_campus.blend --python scripts/run_game.py
```
The intro starts about 1 s after the scene is ready (after run_game's existing still render). Add `-- --no-intro` to skip it.

Intro only (also works without run_game; START then loads the game operator itself):
```
blender output/imrd_campus.blend --python scripts/06_intro_cinematic.py
```
Replay any time: N-panel -> **IMRD Game** -> **Play Cinematic Intro**, or press **R** in the menu.
Tip: maximise the 3D viewport first (Ctrl+Space) for a full-screen cinematic.

## Controls

| Where | Input |
|-------|-------|
| During the intro | **Esc / Enter / Space** or click **SKIP INTRO** -> short fade, then menu |
| Menu | **W/S or Up/Down** select, **Enter/Space** or click to confirm, **R** replay intro |
| Settings | Enter toggles DEPTH OF FIELD / RENDERED VIEW, **Esc** or BACK returns |
| START WALKTHROUGH | fades out, restores the Blender UI, puts the player on the spawn point (0, 68, 0), switches to the gameplay camera and starts `imrd.start_game` once. HUD is created by the game; the mission manager is not touched, so no rewards can be duplicated |
| EXIT | closes the intro and restores the normal Blender UI (does not quit Blender) |

## Timeline (seconds)

| Shot | Time | Camera |
|------|------|--------|
| 1 Fade In | 0-2 | black -> wide view from beyond the gate, slow start |
| 2 Campus Reveal | 2-6 | descends toward the gate, flying **over** the gate arch |
| 3 Entrance Approach | 6-10 | down the central road to the plaza, facade/canopy/entrance |
| 4 Title Reveal | 10-14 | gentle pull-back; IMRD, 3D CAMPUS WALKTHROUGH, institution name fade in |
| 5 Final View | 14-17 | hold on the entrance composition |
| 6 Menu | 17-20 | menu fades in over the held shot |

## Adjusting the shots (no code rewrite)

* On first run the script creates draggable empties in collection **Intro_Cinematic**:
  `IntroCam_00_Establish ...` (camera position) and `IntroLook_00 ...` (look-at point). Move them in the viewport; custom properties `intro_t` (time) and `intro_ease` (stop at this key) are editable. The next play uses them.
* Every path is validated against the real bounding boxes of the building, gate, trees, props and NPCs. If a key would clip, it is lifted over the obstacle; if that fails a safe fallback dolly is used (and printed to the console).
* **Reset Intro Camera Markers** (N-panel) rebuilds them from the current campus layout. Timing/title/palette constants are at the top of `06_intro_cinematic.py`.

## Preview render and self-test

```
blender -b output/imrd_campus.blend --python scripts/06_intro_cinematic.py -- --render-preview
blender -b output/imrd_campus.blend --python scripts/06_intro_cinematic.py -- --selftest
python3 scripts/tests/test_intro_logic.py
```
`--render-preview`: 640x360, 24 fps, 16 samples, EEVEE, frames 1-409, real 3D text objects, fade from/to black. Outputs `output/intro_preview/intro_preview.mp4` (or PNG frames if mp4 is unavailable) plus three stills. The report lists only files that exist on disk. Render the final version at a higher resolution only after approving the preview (edit `res`/`samples` in `render_preview`).

## Notes

* Viewport look: Solid/Material Preview does not use the Nishita sky or sun; choose **Settings -> RENDERED VIEW: ON** for the golden-hour look (heavier on a laptop).
* The intro adds only `Intro_Camera` and the marker empties; the player avatar is hidden during the intro and restored afterwards. If anything fails, the intro restores the viewport, camera and render size automatically.
* While the intro is up, keyboard/mouse input is captured by the intro (other editors are unaffected).
