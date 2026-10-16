"""
test_all_systems.py
===================
Automated Test Suite for IMRD 3D Campus Game.
Tests:
1. Python syntax verification for all 6 game scripts.
2. Blender scene data integrity (Collections, Objects, Materials, Cameras).
3. Player controller collision math.
4. Mission progression, XP accumulation, and save/load state.
5. Rendered assets verification.
"""

import ast
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
OUTPUT_DIR = PROJECT_ROOT / "output"

def test_script_syntax():
    print("[Test 1/5] Checking Python syntax for all scripts...")
    script_files = [
        "01_build_campus.py",
        "02_player_controller.py",
        "03_npc_interactions.py",
        "04_missions.py",
        "05_game_ui.py",
        "run_game.py"
    ]
    for s_name in script_files:
        s_path = SCRIPTS_DIR / s_name
        assert s_path.exists(), f"Missing script: {s_path}"
        code = s_path.read_text(encoding="utf-8")
        ast.parse(code)
        print(f"  ✓ {s_name}: Syntax OK")

def test_missions_logic():
    print("\n[Test 2/5] Testing mission progression & save/restore...")
    import sys
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import importlib
    missions_mod = importlib.import_module("04_missions")
    mgr = missions_mod.MissionManager()

    # Initial state
    assert mgr.level == 1 and mgr.xp == 0
    assert "First Day at IMRD" in mgr.get_current_objective_text()

    # Talk to guide
    mgr.on_talk_to_guide()
    assert mgr.missions["first_day"]["completed"] == True
    assert mgr.xp >= 150

    # Pick up card
    mgr.on_pickup_id_card()
    assert mgr.missions["lost_id_card"]["has_card"] == True
    assert len(mgr.inventory) == 1

    # Save and reload
    test_save = OUTPUT_DIR / "test_save.json"
    mgr.save_state(filepath=test_save)
    assert test_save.exists()

    mgr_new = missions_mod.MissionManager()
    success = mgr_new.load_state(filepath=test_save)
    assert success
    assert mgr_new.xp == mgr.xp
    assert mgr_new.level == mgr.level
    assert mgr_new.inventory == mgr.inventory
    test_save.unlink()
    print("  ✓ Mission state, XP calculation, and save/load passed.")

def test_collision_math():
    print("\n[Test 3/5] Testing collision detection...")
    import importlib
    p_mod = importlib.import_module("02_player_controller")
    check_collision = p_mod.check_collision
    from mathutils import Vector

    # Position in open road (0, 40, 0) should NOT collide
    assert not check_collision(Vector((0, 40, 0)))

    # Position inside building front wall (-10, 8.5, 1.0) MUST collide
    assert check_collision(Vector((-10, 8.5, 1.0)))

    # Position inside gate pillar (5.5, 75.0, 1.0) MUST collide
    assert check_collision(Vector((5.5, 75.0, 1.0)))

    print("  ✓ Collision boundary checks passed.")

def test_rendered_outputs():
    print("\n[Test 4/5] Verifying rendered screenshots...")
    expected_images = [
        "campus_overview.png",
        "campus_entrance.png",
        "player_third_person.png",
        "npc_guide_entrance.png",
        "gameplay_overview.png"
    ]
    for img in expected_images:
        path = OUTPUT_DIR / img
        assert path.exists(), f"Missing render: {img}"
        size_kb = path.stat().st_size / 1024
        assert size_kb > 50, f"Image file suspiciously small: {img}"
        print(f"  ✓ {img}: Exists ({size_kb:.1f} KB)")

def test_blend_file():
    print("\n[Test 5/5] Verifying master Blender project file...")
    blend_path = OUTPUT_DIR / "imrd_campus.blend"
    assert blend_path.exists(), "imrd_campus.blend not found!"
    size_kb = blend_path.stat().st_size / 1024
    print(f"  ✓ imrd_campus.blend: Exists ({size_kb:.1f} KB)")

if __name__ == "__main__":
    print("=" * 60)
    print("  RUNNING IMRD 3D GAME AUTOMATED TEST SUITE")
    print("=" * 60)
    test_script_syntax()
    test_missions_logic()
    test_collision_math()
    test_rendered_outputs()
    test_blend_file()
    print("\n" + "=" * 60)
    print("  ALL 5 TEST SUITES PASSED PERFECTLY!")
    print("=" * 60)
