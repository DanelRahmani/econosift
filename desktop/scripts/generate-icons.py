"""Generate placeholder app icons for Tauri development.

Run from the desktop/ directory:
    python scripts/generate-icons.py

Replace the output with real icons before release.
"""
import struct
import zlib
import os

def create_png(width: int, height: int, r: int = 41, g: int = 98, b: int = 255) -> bytes:
    """Create a minimal valid RGBA PNG file with a solid color."""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    # color_type=6 means RGBA
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))

    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes([r, g, b, 255]) * width

    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def create_ico(png_data: bytes) -> bytes:
    """Create a minimal .ico file from a single 256x256 RGBA PNG image."""
    # ICO header: reserved(2) + type(2) + count(2)
    header = struct.pack("<HHH", 0, 1, 1)
    # Directory entry: width, height, colors, reserved, planes, bpp, size, offset
    # Use 0 for width/height to represent 256x256 (ICO convention)
    size = len(png_data)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, size, 22)
    return header + entry + png_data


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "src-tauri", "icons")
    os.makedirs(out_dir, exist_ok=True)

    sizes = {
        "32x32.png": (32, 32),
        "128x128.png": (128, 128),
        "128x128@2x.png": (256, 256),
    }

    for name, (w, h) in sizes.items():
        data = create_png(w, h)
        path = os.path.join(out_dir, name)
        with open(path, "wb") as f:
            f.write(data)
        print(f"  Created {path} ({w}x{h})")

    # Generate .ico (Windows)
    png_256 = create_png(256, 256)
    ico_data = create_ico(png_256)
    ico_path = os.path.join(out_dir, "icon.ico")
    with open(ico_path, "wb") as f:
        f.write(ico_data)
    print(f"  Created {ico_path}")

    # Generate .icns placeholder (macOS) - just copy PNG for placeholder
    # Real .icns requires a proper converter
    icns_path = os.path.join(out_dir, "icon.icns")
    with open(icns_path, "wb") as f:
        f.write(create_png(256, 256))
    print(f"  Created {icns_path} (placeholder - replace with real .icns)")

    print("\nDone! Replace these placeholder icons with real ones before release.")


if __name__ == "__main__":
    main()
