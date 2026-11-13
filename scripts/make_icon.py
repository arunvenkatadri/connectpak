"""Draw the plugin icons (pixel art, matching docs/assets/connectpak-banner.png).

    uv run --with pillow python scripts/make_icon.py \
        plugins/connectpak/assets/logo.png plugins/connectpak/assets/composer-icon.png
"""
import sys

from PIL import Image, ImageDraw

BG = (18, 14, 24)
OUT = (226, 214, 186)     # cream outline
P1 = (120, 72, 196)       # purple body
P2 = (156, 108, 228)      # purple highlight (tops)
P3 = (82, 46, 140)        # purple shadow
N = 32
img = Image.new("RGB", (N, N), BG)
d = ImageDraw.Draw(img)

def disc(y, h):
    # body of one disc, x 7..24, with elliptical top
    d.rectangle([7, y, 24, y + h], fill=P1)
    d.rectangle([7, y + h - 1, 24, y + h], fill=P3)
    d.line([7, y, 7, y + h], fill=OUT)
    d.line([24, y, 24, y + h], fill=OUT)
    d.line([8, y + h + 1, 23, y + h + 1], fill=OUT)

def top(y):
    d.rectangle([9, y - 2, 22, y + 2], fill=P2)
    d.rectangle([8, y - 1, 23, y + 1], fill=P2)
    d.line([10, y - 3, 21, y - 3], fill=OUT)
    d.point([(9, y - 2), (22, y - 2), (8, y - 1), (23, y - 1)], fill=OUT)
    d.point([(7, y), (24, y)], fill=OUT)

for y in (19, 14, 9):  # bottom to top
    disc(y, 5)
top(9)
# separator highlights between discs
for y in (14, 19):
    d.line([8, y, 23, y], fill=P2)
# connector plug, right side
d.rectangle([25, 20, 27, 21], fill=OUT)
d.rectangle([27, 18, 29, 23], fill=OUT)
d.rectangle([28, 19, 28, 22], fill=BG)

for size, path in ((512, sys.argv[1]), (128, sys.argv[2])):
    img.resize((size, size), Image.NEAREST).save(path, optimize=True)
