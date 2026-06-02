"""Generate a themed placeholder profile image for the About page.

Run: python scripts/make_profile_placeholder.py
Replace public/profile.png with a real photo whenever you like — same path,
same square aspect, and the About page picks it up with no code change.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

W = H = 600
BASE = (10, 12, 16)       # base
PANEL = (17, 21, 28)      # panel
FG = (180, 190, 202)      # slightly brighter ink-muted for the silhouette
ACCENT = (57, 208, 216)   # accent


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# Radial gradient backdrop: a subtle accent-tinted glow off the top, fading to
# base at the edges so it reads well once the image is cropped to a circle.
glow_center = (int(W * 0.42), int(H * 0.34))
accent_dark = lerp(PANEL, ACCENT, 0.22)
max_r = math.hypot(W, H)

img = Image.new("RGB", (W, H), BASE)
px = img.load()
for y in range(H):
    for x in range(W):
        dist = math.hypot(x - glow_center[0], y - glow_center[1]) / (max_r * 0.6)
        t = min(max(dist, 0.0), 1.0)
        px[x, y] = lerp(accent_dark, BASE, t)

d = ImageDraw.Draw(img)

# avatar silhouette: head + shoulders, centered
cx = W // 2
hr = 92
hy = 222
d.ellipse([cx - hr, hy - hr, cx + hr, hy + hr], fill=FG)

bw = 330
bx0, bx1 = cx - bw // 2, cx + bw // 2
by0, by1 = 352, 640
d.pieslice([bx0, by0, bx1, by0 + 2 * (by1 - by0)], 180, 360, fill=FG)

out = Path(__file__).resolve().parent.parent / "public" / "profile.png"
img.save(out, "PNG")
print(f"written {out}")
