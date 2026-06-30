"""Generate placeholder icons for Tauri development.

Creates a single large RGBA PNG source image, then uses `npx tauri icon`
to generate all required platform icons (ICO, ICNS, PNGs at correct sizes).

Prerequisites: `npm install` in desktop/ already ran.

Usage from desktop/:
    python scripts/generate-icons.py
"""
import struct
import zlib
import subprocess
import sys
from pathlib import Path


def create_png(width: int, height: int, r: int = 41, g: int = 98, b: int = 255) -> bytes:
    """Create a minimal valid RGBA PNG file with a solid color."""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))

    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes([r, g, b, 255]) * width

    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def main():
    root = Path(__file__).resolve().parent.parent
    icons_dir = root / "src-tauri" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Generate a single 1024x1024 RGBA source PNG
    source_png = root / "app-icon.png"
    data = create_png(1024, 1024)
    source_png.write_bytes(data)
    print(f"Created source icon: {source_png} (1024x1024 RGBA)")

    # Use Tauri CLI to generate all platform icons
    print("Running `tauri icon` to generate platform icons...")
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    result = subprocess.run(
        [npx, "tauri", "icon", str(source_png)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("tauri icon failed:", result.stderr, file=sys.stderr)
        sys.exit(1)
    print(result.stdout)

    # Clean up source
    source_png.unlink()
    print(f"\nDone! Platform icons generated in {icons_dir}")


if __name__ == "__main__":
    main()
