import struct
from pathlib import Path

def build_iso(out_path: Path, files: dict, volume_id: str = "cidata"):
    SECTOR = 2048
    img = bytearray(32768) # 16 sectors

    # Prepare file data sectors
    cur_sector = 21
    file_info = {}
    for fname, data in files.items():
        n_sectors = (len(data) + SECTOR - 1) // SECTOR or 1
        file_info[fname] = (cur_sector, len(data), data)
        cur_sector += n_sectors

    total_sectors = cur_sector + 2

    # PVD
    pvd = bytearray(SECTOR)
    pvd[0] = 0x01
    pvd[1:6] = b"CD001"
    pvd[6] = 0x01
    pvd[8:40] = b"LINUX".ljust(32, b" ")
    pvd[40:72] = volume_id.encode("ascii").ljust(32, b" ")
    struct.pack_into("<II", pvd, 80, total_sectors, total_sectors)
    struct.pack_into("<HHHH", pvd, 120, 1, 1, 1, 1)
    struct.pack_into("<HH", pvd, 128, SECTOR, SECTOR)
    struct.pack_into("<II", pvd, 132, 10, 10)
    struct.pack_into("<I", pvd, 140, 18)
    struct.pack_into(">I", pvd, 148, 19)

    root_rec = bytearray(34)
    root_rec[0] = 34
    struct.pack_into("<II", root_rec, 2, 20, 20)
    struct.pack_into("<II", root_rec, 10, SECTOR, SECTOR)
    root_rec[25] = 0x02
    root_rec[32] = 1
    root_rec[33] = 0
    pvd[156:190] = root_rec
    pvd[881] = 0x01
    img.extend(pvd)

    # VD Terminator
    vdt = bytearray(SECTOR)
    vdt[0] = 0xFF
    vdt[1:6] = b"CD001"
    vdt[6] = 0x01
    img.extend(vdt)

    # Path Tables
    pt_l = bytearray(SECTOR)
    pt_l[0] = 1
    struct.pack_into("<I", pt_l, 2, 20)
    struct.pack_into("<H", pt_l, 6, 1)
    img.extend(pt_l)

    pt_m = bytearray(SECTOR)
    pt_m[0] = 1
    struct.pack_into(">I", pt_m, 2, 20)
    struct.pack_into(">H", pt_m, 6, 1)
    img.extend(pt_m)

    # Root Directory Record
    rdir = bytearray(SECTOR)
    offset = 0

    def add_rec(lba, size, is_dir, name_b):
        nonlocal offset
        rec_len = 33 + len(name_b)
        if rec_len % 2 != 0:
            rec_len += 1
        rec = bytearray(rec_len)
        rec[0] = rec_len
        struct.pack_into("<II", rec, 2, lba, lba)
        struct.pack_into("<II", rec, 10, size, size)
        rec[25] = 0x02 if is_dir else 0x00
        rec[32] = len(name_b)
        rec[33:33+len(name_b)] = name_b
        rdir[offset:offset+rec_len] = rec
        offset += rec_len

    add_rec(20, SECTOR, True, b"\x00")
    add_rec(20, SECTOR, True, b"\x01")
    for fname, (lba, size, _) in file_info.items():
        add_rec(lba, size, False, fname.encode("ascii") + b";1")

    img.extend(rdir)

    # File Sectors
    for fname, (lba, size, data) in file_info.items():
        sec = bytearray(((len(data) + SECTOR - 1) // SECTOR) * SECTOR)
        sec[:len(data)] = data
        img.extend(sec)

    while len(img) < total_sectors * SECTOR:
        img.extend(bytearray(SECTOR))

    out_path.write_bytes(img)
    print(f"Generated cloud-init ISO: {out_path} ({len(img)} bytes)")

