"""
test_import_assets.py
Test script to verify appending models from assets/New Modle.
"""

import bpy
from pathlib import Path
from mathutils import Vector, Matrix
import math

PROJECT_ROOT = Path(r"C:\Users\krish\.gemini\antigravity-ide\scratch\IMRD-Blender-Game")
ASSETS_DIR = PROJECT_ROOT / "assets" / "New Modle"

def test_single():
    # Test Mercedes
    p = ASSETS_DIR / "32-mercedes-benz-gls-580-2020" / "uploads_files_2787791_Mercedes+Benz+GLS+580.blend"
    with bpy.data.libraries.load(str(p)) as (df, dt):
        dt.objects = [o for o in df.objects if "mercedes" in o.lower() and not "camera" in o.lower()]
    print("Loaded objects:", [o.name for o in dt.objects if o])

if __name__ == "__main__":
    test_single()
