"""Plain-Python tests for the intro logic (no Blender needed):
    python3 scripts/tests/test_intro_logic.py
"""
import importlib.util
import sys
from pathlib import Path

cand_paths = [
    Path(__file__).resolve().parent / "06_intro_cinematic.py",
    Path(__file__).resolve().parent / "scripts" / "06_intro_cinematic.py",
    Path(__file__).resolve().parents[1] / "06_intro_cinematic.py",
    Path(__file__).resolve().parents[1] / "scripts" / "06_intro_cinematic.py",
]
p = next((cp for cp in cand_paths if cp.exists()), cand_paths[0])
spec = importlib.util.spec_from_file_location("intro06", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
res = m.selftest()
for r in res:
    print(f"[{r[2]:4}] {r[0]:>4} {r[1]} - {r[3]}")
bad = [r for r in res if r[2] != "PASS"]
print(f"\n{len(res) - len(bad)}/{len(res)} passed")
sys.exit(1 if bad else 0)
