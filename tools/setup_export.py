import os
import shutil
from pathlib import Path

appdata = os.environ.get("APPDATA")
src_exe = Path(os.environ.get("LOCALAPPDATA")) / "Microsoft/WinGet/Packages/GodotEngine.GodotEngine_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.2-stable_win64.exe"
dest_dir = Path(appdata) / "Godot/export_templates/4.7.2.stable"

dest_dir.mkdir(parents=True, exist_ok=True)
print(f"Source exe exists: {src_exe.exists()} ({src_exe})")
print(f"Target dir: {dest_dir}")

for name in ["windows_release_x86_64.exe", "windows_debug_x86_64.exe"]:
    target = dest_dir / name
    if not target.exists() or target.stat().st_size != src_exe.stat().st_size:
        print(f"Copying to {target}...")
        shutil.copy2(src_exe, target)
        print("Done.")
    else:
        print(f"Already exists: {target}")
