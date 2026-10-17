import struct, hashlib
from pathlib import Path

pck_src = Path('output/builds/windows/IMRD_Campus_Explorer.pck.bak')
pck_dst = Path('output/builds/windows/IMRD_Campus_Explorer.pck')

with open(pck_src, 'rb') as f:
    hdr = bytearray(f.read(112))
    f.seek(32)
    dir_offset = struct.unpack('<Q', f.read(8))[0]
    f.seek(dir_offset)
    count = struct.unpack('<I', f.read(4))[0]
    entries = []
    for _ in range(count):
        slen = struct.unpack('<I', f.read(4))[0]
        raw = f.read(slen)
        path = raw.rstrip(b'\x00').decode('utf-8')
        off, size = struct.unpack('<QQ', f.read(16))
        md5 = f.read(16)
        flags = struct.unpack('<I', f.read(4))[0]
        entries.append({'path': path, 'offset': off, 'size': size, 'md5': md5, 'flags': flags})
        
    file_base = 112
    files_data = {}
    for e in entries:
        f.seek(file_base + e['offset'])
        files_data[e['path']] = f.read(e['size'])

# 1. Update portico scn (clean of AC compressors, 11.95m board)
portico_key = '.godot/exported/133200997/export-5f3a24acc98a1f29897e23abcb9d8362-imrd_entrance_portico.scn'
with open('game/' + portico_key, 'rb') as f:
    files_data[portico_key] = f.read()

# 2. Add raw campus_visual_enhancer.gd
with open('game/scripts/campus_visual_enhancer.gd', 'rb') as f:
    enhancer_gd = f.read()

# Point remap to .gd instead of .gdc
remap_key = 'scripts/campus_visual_enhancer.gd.remap'
files_data[remap_key] = b'[remap]\n\npath="res://scripts/campus_visual_enhancer.gd"\n'

# Add scripts/campus_visual_enhancer.gd to files_data and entries
gd_key = 'scripts/campus_visual_enhancer.gd'
files_data[gd_key] = enhancer_gd
entries.append({'path': gd_key, 'offset': 0, 'size': len(enhancer_gd), 'md5': hashlib.md5(enhancer_gd).digest(), 'flags': 0})

# Repack
with open(pck_dst, 'wb') as out:
    out.write(hdr)
    new_entries = []
    curr_off = 0
    for e in entries:
        data = files_data[e['path']]
        pad = (16 - (curr_off % 16)) % 16
        if pad:
            out.write(b'\x00' * pad)
            curr_off += pad
        entry_off = curr_off
        out.write(data)
        curr_off += len(data)
        new_entries.append({
            'path': e['path'],
            'offset': entry_off,
            'size': len(data),
            'md5': hashlib.md5(data).digest(),
            'flags': e['flags']
        })
    pad = (16 - (curr_off % 16)) % 16
    if pad:
        out.write(b'\x00' * pad)
        curr_off += pad
    dir_offset = 112 + curr_off
    out.write(struct.pack('<I', len(new_entries)))
    for ne in new_entries:
        p_bytes = ne['path'].encode('utf-8')
        p_pad = (4 - (len(p_bytes) % 4)) % 4
        padded = p_bytes + b'\x00' * p_pad
        out.write(struct.pack('<I', len(padded)))
        out.write(padded)
        out.write(struct.pack('<QQ', ne['offset'], ne['size']))
        out.write(ne['md5'])
        out.write(struct.pack('<I', ne['flags']))
    total_size = out.tell()
    out.seek(32)
    out.write(struct.pack('<Q', dir_offset))

print(f'Repack completed: total_size={total_size}, dir_offset={dir_offset}')
