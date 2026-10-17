import struct
import hashlib
from pathlib import Path

def repack():
    pck_path = Path("output/builds/windows/IMRD_Campus_Explorer.pck")
    pck_bak = Path("output/builds/windows/IMRD_Campus_Explorer.pck.bak2")
    
    # Keep a fresh backup if not already made
    if not pck_bak.exists():
        with open(pck_path, "rb") as src, open(pck_bak, "wb") as dst:
            dst.write(src.read())
            
    with open(pck_path, "rb") as f:
        header = bytearray(f.read(112))
        f.seek(32)
        dir_offset = struct.unpack("<Q", f.read(8))[0]
        f.seek(dir_offset)
        file_count = struct.unpack("<I", f.read(4))[0]
        
        entries = []
        for _ in range(file_count):
            slen = struct.unpack("<I", f.read(4))[0]
            path = f.read(slen).decode("utf-8").rstrip("\x00")
            offset, size = struct.unpack("<QQ", f.read(16))
            md5 = f.read(16)
            flags = struct.unpack("<I", f.read(4))[0]
            entries.append({"path": path, "offset": offset, "size": size, "flags": flags, "md5": md5})
            
        file_base = 112
        files_data = {}
        for e in entries:
            f.seek(file_base + e["offset"])
            files_data[e["path"]] = f.read(e["size"])
            
    # Load updated files from disk
    with open("game/scripts/campus_visual_enhancer.gd", "rb") as f:
        enhancer_gd = f.read()
    with open("game/scripts/test_runner.gd", "rb") as f:
        test_runner_gd = f.read()
    with open("game/scenes/campus.tscn", "rb") as f:
        campus_tscn = f.read()
    with open("game/scenes/classroom_door.tscn", "rb") as f:
        classroom_door_tscn = f.read()
    with open("game/scripts/procedural_bookshelf.gd", "rb") as f:
        procedural_bookshelf_gd = f.read()
    with open("game/scenes/procedural_bookshelf.tscn", "rb") as f:
        procedural_bookshelf_tscn = f.read()
        
    # Store or update in files_data
    files_data["scripts/campus_visual_enhancer.gd"] = enhancer_gd
    files_data["scripts/test_runner.gd"] = test_runner_gd
    files_data["scenes/campus.tscn"] = campus_tscn
    files_data["scenes/classroom_door.tscn"] = classroom_door_tscn
    files_data["scripts/procedural_bookshelf.gd"] = procedural_bookshelf_gd
    files_data["scenes/procedural_bookshelf.tscn"] = procedural_bookshelf_tscn
    
    # Update remap entries
    files_data["scripts/campus_visual_enhancer.gd.remap"] = b'[remap]\n\npath="res://scripts/campus_visual_enhancer.gd"\n'
    files_data["scripts/test_runner.gd.remap"] = b'[remap]\n\npath="res://scripts/test_runner.gd"\n'
    files_data["scenes/campus.tscn.remap"] = b'[remap]\n\npath="res://scenes/campus.tscn"\n'
    files_data["scenes/classroom_door.tscn.remap"] = b'[remap]\n\npath="res://scenes/classroom_door.tscn"\n'
    files_data["scripts/procedural_bookshelf.gd.remap"] = b'[remap]\n\npath="res://scripts/procedural_bookshelf.gd"\n'
    files_data["scenes/procedural_bookshelf.tscn.remap"] = b'[remap]\n\npath="res://scenes/procedural_bookshelf.tscn"\n'
    
    # Ensure entry list contains all keys
    entry_keys = {e["path"] for e in entries}
    for new_key in [
        "scripts/campus_visual_enhancer.gd", "scripts/test_runner.gd",
        "scenes/campus.tscn", "scenes/classroom_door.tscn",
        "scripts/procedural_bookshelf.gd", "scenes/procedural_bookshelf.tscn",
        "scripts/procedural_bookshelf.gd.remap", "scenes/procedural_bookshelf.tscn.remap"
    ]:
        if new_key not in entry_keys:
            entries.append({"path": new_key, "offset": 0, "size": len(files_data[new_key]), "flags": 0, "md5": b"\x00"*16})

    # Now repack with 16-byte alignment
    pck_tmp = Path("output/builds/windows/IMRD_Campus_Explorer.pck.tmp")
    with open(pck_tmp, "wb") as out:
        out.write(header) # placeholder
        
        current_off = 0
        file_base = 112
        new_entries = []
        for e in entries:
            path = e["path"]
            data = files_data[path]
            
            # Align to 16 bytes
            padding_len = (16 - (current_off % 16)) % 16
            if padding_len > 0:
                out.write(b"\x00" * padding_len)
                current_off += padding_len
                
            file_off = current_off
            out.write(data)
            current_off += len(data)
            
            h = hashlib.md5(data).digest()
            new_entries.append({
                "path": path,
                "offset": file_off,
                "size": len(data),
                "flags": e.get("flags", 0),
                "md5": h
            })
            
        # Write directory
        dir_off = current_off + file_base
        out.write(struct.pack("<I", len(new_entries)))
        for ne in new_entries:
            p_bytes = ne["path"].encode("utf-8")
            pad = (4 - (len(p_bytes) % 4)) % 4
            p_bytes_padded = p_bytes + b"\x00" * pad
            out.write(struct.pack("<I", len(p_bytes_padded)))
            out.write(p_bytes_padded)
            out.write(struct.pack("<QQ", ne["offset"], ne["size"]))
            out.write(ne["md5"])
            out.write(struct.pack("<I", ne["flags"]))
            
        # Update header
        out.seek(0)
        # Magic GDPC
        header[0:4] = b"GDPC"
        # Version 2
        struct.pack_into("<I", header, 4, 2)
        # Godot 4.7.2
        struct.pack_into("<III", header, 8, 4, 7, 2)
        # Reserved
        header[20:32] = b"\x00" * 12
        # Directory offset
        struct.pack_into("<Q", header, 32, dir_off)
        out.write(header)
        
    pck_tmp.replace(pck_path)
    print(f"Successfully repacked {pck_path}: size={pck_path.stat().st_size}, dir_offset={dir_off}, files={len(new_entries)}")

if __name__ == "__main__":
    repack()
