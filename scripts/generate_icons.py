"""
Script to generate app icons (192x192, 512x512, 72x72) in pure Python without external dependencies.
Uses minimal PNG chunk writer.
"""
import os
import struct
import zlib

def make_png(width, height, color_bg=(124, 58, 237), color_accent=(6, 182, 212)):
    # Create raw pixel data (RGBA)
    raw = bytearray()
    center_x = width // 2
    center_y = height // 2
    radius = int(min(width, height) * 0.42)
    inner_radius = int(radius * 0.75)

    for y in range(height):
        raw.append(0)  # Filter byte for PNG scanline
        for x in range(width):
            dist_sq = (x - center_x) ** 2 + (y - center_y) ** 2
            if dist_sq <= radius ** 2:
                # Inside outer circle
                if dist_sq <= (radius * 0.88) ** 2 and dist_sq >= (radius * 0.75) ** 2:
                    # Ring
                    r, g, b, a = color_accent[0], color_accent[1], color_accent[2], 255
                elif dist_sq <= (radius * 0.2) ** 2:
                    # Center dot
                    r, g, b, a = 255, 255, 255, 255
                else:
                    # Gradient bg
                    t = y / height
                    r = int(color_bg[0] * (1 - t) + 37 * t)
                    g = int(color_bg[1] * (1 - t) + 99 * t)
                    b = int(color_bg[2] * (1 - t) + 235 * t)
                    a = 255
            else:
                # Rounded square background or transparent outside
                corner_radius = int(width * 0.22)
                # Check rounded rect
                dx = max(0, abs(x - center_x) - (width // 2 - corner_radius))
                dy = max(0, abs(y - center_y) - (height // 2 - corner_radius))
                if dx * dx + dy * dy <= corner_radius * corner_radius:
                    r, g, b, a = 26, 26, 46, 255
                else:
                    r, g, b, a = 0, 0, 0, 0
            raw.extend([r, g, b, a])

    # PNG chunks
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)

    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
    return png

def main():
    icons_dir = os.path.join(os.path.dirname(__file__), "..", "static", "icons")
    os.makedirs(icons_dir, exist_ok=True)

    sizes = {
        "icon-192.png": (192, 192),
        "icon-512.png": (512, 512),
        "badge-72.png": (72, 72),
    }

    for name, (w, h) in sizes.items():
        path = os.path.join(icons_dir, name)
        png_data = make_png(w, h)
        with open(path, "wb") as f:
            f.write(png_data)
        print(f"Generated {name} ({w}x{h})")

if __name__ == "__main__":
    main()
