import struct
import shutil
import zipfile
from pathlib import Path

def build_standalone():
    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / "output" / "builds" / "windows"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    godot_exe = Path(r"C:\Users\krish\AppData\Local\Microsoft\WinGet\Packages\GodotEngine.GodotEngine_Microsoft.Winget.Source_8wekyb3d8bbwe\Godot_v4.7.2-stable_win64.exe")
    pck_file = output_dir / "IMRD_Campus_Explorer.pck"
    
    if not godot_exe.exists():
        raise FileNotFoundError(f"Godot binary not found at {godot_exe}")
    if not pck_file.exists():
        raise FileNotFoundError(f"PCK file not found at {pck_file}")
        
    print(f"Reading Godot base binary: {godot_exe} ({godot_exe.stat().st_size} bytes)")
    with open(godot_exe, "rb") as f:
        exe_bytes = f.read()
        
    print(f"Reading game PCK: {pck_file} ({pck_file.stat().st_size} bytes)")
    with open(pck_file, "rb") as f:
        pck_bytes = f.read()
        
    pck_len = len(pck_bytes)
    # Godot embedded PCK footer format:
    # 8-byte uint64: length of PCK data
    # 4-byte uint32: magic 0x43504447 ('GDPC')
    footer = struct.pack("<QI", pck_len, 0x43504447)
    
    target_exe = output_dir / "IMRD_Campus_Explorer.exe"
    print(f"Writing self-contained single executable to: {target_exe}")
    with open(target_exe, "wb") as f:
        f.write(exe_bytes)
        f.write(pck_bytes)
        f.write(footer)
        
    total_size_mb = target_exe.stat().st_size / (1024 * 1024)
    print(f"Successfully created {target_exe.name} ({total_size_mb:.2f} MB)")
    
    # Also write a friendly README for friends
    readme_path = output_dir / "HOW_TO_PLAY.txt"
    readme_content = """============================================================
  RCPET IMRD Shirpur — 3D Campus Explorer Game
============================================================

HOW TO PLAY:
1. Double-click "IMRD_Campus_Explorer.exe" to start the game.
   (No installation or extra files required!)

CONTROLS:
- W, A, S, D or Arrow Keys : Move character
- Mouse Movement           : Rotate camera / look around
- Left Shift (Hold)        : Sprint
- Spacebar                 : Jump
- E                        : Interact (Talk to Prof. Sharma, pick up ID card, open doors)
- Escape or Q              : Pause Menu / Settings

CAMPUS MISSIONS:
- Mission 1: Talk to Prof. Sharma at the entrance walkway.
- Mission 2: Find and pick up the lost Student ID Card near the crossing.
- Mission 3: Explore Classroom West, Grand Lobby, and Garden Courtyard.

Enjoy exploring the RCPET IMRD campus!
============================================================
"""
    readme_path.write_text(readme_content, encoding="utf-8")
    print(f"Created {readme_path}")
    
    # Create a ready-to-share ZIP file for friends
    zip_dest = output_dir / "IMRD_Campus_Explorer_Shareable.zip"
    print(f"Packaging shareable ZIP archive to: {zip_dest} ...")
    with zipfile.ZipFile(zip_dest, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(target_exe, arcname="IMRD_Campus_Explorer.exe")
        z.write(readme_path, arcname="HOW_TO_PLAY.txt")
        
    zip_size_mb = zip_dest.stat().st_size / (1024 * 1024)
    print(f"Created shareable zip: {zip_dest} ({zip_size_mb:.2f} MB)")

if __name__ == "__main__":
    build_standalone()
