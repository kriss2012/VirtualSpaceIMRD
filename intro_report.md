# IMRD Intro Cinematic - Test Report

Generated: 2026-10-16 21:41:56  
Blender: not run in Blender  
Python: 3.13.16

## Files

- scripts/06_intro_cinematic.py (new)
- scripts/run_game.py (4 small edits marked [INTRO INTEGRATION n/4]: optional import, `_running` guard on `imrd.start_game`, register, autostart)
- README_INTRO.md (new)
- scripts/tests/test_intro_logic.py (new)

## Timeline

- Shot 1 Fade In: 0-2 s
- Shot 2 Campus Reveal: 2-6 s
- Shot 3 Entrance Approach: 6-10 s
- Shot 4 Title Reveal: 10-14 s
- Shot 5 Final Establishing View: 14-17 s
- Shot 6 Main Menu: 17-20 s

Camera keys (time, position, look-at):

- Establish: t=0.0  pos=(24.0, 90.0, 15.5)  look=(0.0, 40.0, 3.5)  (ease)
- Reveal: t=2.0  pos=(20.7, 84.9, 14.4)  look=(0.0, 38.0, 3.4)
- OverGate: t=6.0  pos=(2.0, 56.0, 8.0)  look=(0.0, 22.1, 3.2)
- Entrance: t=10.0  pos=(-2.5, 21.1, 2.0)  look=(0.0, 9.1, 3.6)  (ease)
- PullBack: t=14.0  pos=(-1.8, 38.0, 3.4)  look=(-4.5, 9.6, 6.4)
- Hold: t=17.0  pos=(-2.0, 41.8, 3.6)  look=(-4.5, 9.6, 6.4)
- End: t=20.0  pos=(-2.1, 42.6, 3.7)  look=(-4.5, 9.6, 6.4)  (ease)

## Test results

| # | Test | Result | Detail |
|---|------|--------|--------|
| 04 | Camera motion smooth (no jumps, bounded speed/rotation) | PASS | max speed 11.9 m/s, max camera turn 7.8 deg/s, max step 5.0 cm @240Hz, start/end speed 0.01/0.00 |
| 06 | Camera never inside buildings/trees/gate/lamps, never below ground height | PASS | 64 obstacles, margin 0.6 m, lowest z 2.00 m, issues: [] |
| 05 | Main building stays inside the view cone for the whole path | PASS | max angle between view axis and building centre 11.9 deg (half-FOV 32.7) |
| 07 | Title/menu layout valid at 6 window sizes (in bounds, no overlaps, text shrinks to fit) | PASS | [] |
| 08 | Skip (Esc/Space) leads to menu via fade; repeated presses ignored | PASS | state=MENU, t=17.7s |
| 09 | Menu appears (naturally at 17 s and after skip) | PASS | menu alpha 1.00 |
| 09b | Natural playback reaches MENU at t>=17 s | PASS | state=MENU |
| 10 | START WALKTHROUGH fires exactly once despite repeated Enter/clicks | PASS | start_game calls=1, state=DONE |
| 13 | Replay x3 restarts timeline without side effects (no extra start/exit calls) | PASS | replays=3, starts=0, state after each: ['PLAY', 'PLAY', 'PLAY'] |
| 14a | If the game cannot start the menu stays usable (retry possible) | PASS | state=MENU |
| 14b | Settings: toggles work, Esc returns to menu | PASS | dof=False |
| 14 | Layout without scene objects: keys derive from anchors; fallback dolly is collision-free | PASS | fallback issues: [] |
| 14c | Colliding key is lifted over the obstacle | PASS | z -> 6.8 |
| 01 | Intro scene loads in Blender | NOT RUN | needs Blender: campus objects found, intro camera created |
| 02 | Intro_Camera is the active camera | NOT RUN | needs Blender: scene.camera after begin() |
| 03 | Animation starts automatically | NOT RUN | needs Blender: run_game.py autostart / --python 06_intro_cinematic.py |
| 11 | START WALKTHROUGH activates gameplay; player moves | NOT RUN | needs Blender: needs interactive session |
| 12 | HUD and missions still work after the transition | NOT RUN | needs Blender: needs interactive session |
| 15 | Project can be saved and reopened with the intro installed | NOT RUN | needs Blender: needs Blender |
| R1 | Preview render (stills + mp4) produced and checked | NOT RUN | needs Blender: python scripts/06_intro_cinematic.py -- --render-preview |

## Preview output

- No preview was rendered in this run (no render output exists). Run the --render-preview command from the README.

## Remaining limitations

- Blender-specific code (draw handler, modal operator, game hand-off, render preview) was written against the Blender 5.x API but could NOT be executed in the authoring environment; items marked NOT RUN must be verified on your machine.
- Preview render uses text objects with approximate (not pixel-identical) typography; the gold rule line and the menu are viewport overlays and are not part of the rendered video.
- EXIT closes the intro and restores the normal Blender UI; it does not quit Blender.
- Viewport lighting: in Solid/Material Preview the Nishita sky and sun are not used; switch to Rendered (Settings > RENDERED VIEW) for the golden-hour look.
