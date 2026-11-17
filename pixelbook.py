"""Pixel color-by-number page generator.

Turns an image into a print-ready PDF spread:
  page 1 = legend (codes used on this picture, colour name, cell count)
  page 2 = grid to colour (black page, white cells, grey code in each cell)
  page 3 = answer key (filled preview, for QC / back-of-book)

Usage:
  python pixelbook.py input.png -o out.pdf --title "Sunset" [--cols 40 --rows 54] [--shape square|circle] [--hex]
"""
import argparse
from collections import Counter

from PIL import Image, ImageEnhance, ImageOps
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

# 23 marker colours + white. Single-char codes; I and O skipped so they can't be read as 1 and 0.
PALETTE = [
    ("0", "Black", (30, 30, 30)),
    ("1", "Gray", (150, 150, 150)),
    ("2", "Dark Gray", (85, 85, 85)),
    ("3", "Dark Brown", (92, 58, 38)),
    ("4", "Brown", (150, 95, 55)),
    ("5", "Tan", (215, 185, 140)),
    ("6", "Peach", (250, 200, 170)),
    ("7", "Red", (210, 40, 45)),
    ("8", "Red Orange", (235, 90, 50)),
    ("9", "Orange", (245, 150, 40)),
    ("A", "Yellow Orange", (250, 190, 40)),
    ("B", "Yellow", (250, 230, 70)),
    ("C", "Yellow Green", (180, 215, 70)),
    ("D", "Green", (80, 175, 80)),
    ("E", "Dark Green", (30, 110, 70)),
    ("F", "Aqua Green", (60, 190, 170)),
    ("G", "Light Blue", (150, 210, 240)),
    ("H", "Blue", (40, 150, 220)),
    ("J", "Dark Blue", (40, 60, 160)),
    ("K", "Pink", (245, 150, 190)),
    ("L", "Violet", (150, 90, 200)),
    ("M", "Dark Violet", (90, 50, 140)),
    ("N", "Magenta", (220, 50, 140)),
    ("W", "White (leave blank)", (255, 255, 255)),
]
WHITE_CODE = "W"

# KDP full-bleed 8.5x11 interior: 8.625 x 11.25 in (black pages must bleed).
INCH = 72
PAGE_W, PAGE_H = 8.625 * INCH, 11.25 * INCH
MARGIN = 0.7 * INCH  # 0.125 bleed + 0.575 in: meets KDP gutter for books up to 300 pages


def _lab(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


_PAL_LAB = [(code, _lab(rgb)) for code, _, rgb in PALETTE]
_RGB = {code: rgb for code, _, rgb in PALETTE}
_NAME = {code: name for code, name, _ in PALETTE}


def nearest(rgb):
    # shortcut: CIE76 distance, good enough for flat illustration input; switch to CIEDE2000 if photos map badly.
    L = _lab(rgb)
    return min(_PAL_LAB, key=lambda p: sum((a - b) ** 2 for a, b in zip(L, p[1])))[0]


assert all(nearest(rgb) == code for code, _, rgb in PALETTE), "palette colours must map to themselves"


def is_photo(img):
    # Flat art / pixel art has few distinct colours; photos and soft AI renders have thousands.
    return len(img.resize((128, 128)).getcolors(128 * 128)) > 3000


def limit_colors(grid, max_colors):
    """Fold the least-used codes into their nearest remaining code until max_colors remain."""
    lab = dict(_PAL_LAB)
    counts = Counter(x for row in grid for x in row)
    remap = {}
    while len(counts) > max_colors:
        drop = min(counts, key=counts.get)
        target = min((k for k in counts if k != drop),
                     key=lambda k: sum((a - b) ** 2 for a, b in zip(lab[drop], lab[k])))
        counts[target] += counts.pop(drop)
        remap = {k: (target if v == drop else v) for k, v in remap.items()}
        remap[drop] = target
    return [[remap.get(x, x) for x in row] for row in grid], sorted(remap)


def clean_isolated(grid):
    """Replace cells with no same-code neighbour (8-way) by their neighbours' majority code. Returns count."""
    rows, cols = len(grid), len(grid[0])
    src = [row[:] for row in grid]
    changed = 0
    for r in range(rows):
        for c in range(cols):
            nb = [src[rr][cc] for rr in range(max(0, r - 1), min(rows, r + 2))
                  for cc in range(max(0, c - 1), min(cols, c + 2)) if (rr, cc) != (r, c)]
            if src[r][c] not in nb:
                grid[r][c] = Counter(nb).most_common(1)[0][0]
                changed += 1
    return changed


def convert(path, cols, rows, max_colors=15):
    """Image -> grid of codes. Photos get a contrast/saturation boost and speckle cleanup;
    flat art is left alone so intentional single-pixel sparkles survive."""
    img = Image.open(path).convert("RGB")
    photo = is_photo(img)
    if photo:
        img = ImageEnhance.Color(ImageOps.autocontrast(img, cutoff=1)).enhance(1.3)
    grid = image_to_codes(img, cols, rows)
    grid, dropped = limit_colors(grid, max_colors)
    cleaned = clean_isolated(grid) if photo else 0
    return grid, {"photo": photo, "dropped": dropped, "cleaned": cleaned}


def image_to_codes(img, cols, rows, sub=4):
    # Map sub x sub samples per cell to the palette, then take the majority code:
    # plain averaging blends colours at shape edges into extra, muddy codes.
    img = ImageOps.fit(img, (cols * sub, rows * sub), Image.Resampling.BOX)  # centre-crop to grid aspect
    px = img.load()
    cache = {}

    def code_at(x, y):
        rgb = px[x, y]
        if rgb not in cache:
            cache[rgb] = nearest(rgb)
        return cache[rgb]

    grid = [[Counter(code_at(c * sub + i, r * sub + j) for i in range(sub) for j in range(sub)).most_common(1)[0][0]
             for c in range(cols)] for r in range(rows)]
    assert len(grid) == rows and all(len(row) == cols for row in grid)
    return grid


def _grid_geometry(cols, rows, hex_offset):
    eff_cols = cols + (0.5 if hex_offset else 0)
    cell = min((PAGE_W - 2 * MARGIN) / eff_cols, (PAGE_H - 2 * MARGIN) / rows)
    x0 = (PAGE_W - eff_cols * cell) / 2
    y0 = (PAGE_H + rows * cell) / 2  # top edge, reportlab y grows upward
    return cell, x0, y0


def _black_page(c):
    c.setFillColorRGB(0, 0, 0)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)


def draw_grid(c, grid, shape, hex_offset, filled):
    rows, cols = len(grid), len(grid[0])
    cell, x0, y0 = _grid_geometry(cols, rows, hex_offset)
    gap = cell * 0.12
    size = cell - gap
    font_size = cell * 0.48
    _black_page(c)
    c.setFont("Helvetica", font_size)
    for r, row in enumerate(grid):
        shift = cell / 2 if hex_offset and r % 2 else 0
        for col, code in enumerate(row):
            x = x0 + col * cell + shift + gap / 2
            y = y0 - (r + 1) * cell + gap / 2
            fill = _RGB[code] if filled else (255, 255, 255)
            c.setFillColorRGB(*(v / 255 for v in fill))
            if shape == "circle":
                c.circle(x + size / 2, y + size / 2, size / 2, stroke=0, fill=1)
            else:
                c.roundRect(x, y, size, size, size * 0.18, stroke=0, fill=1)
            if not filled:
                c.setFillColor(Color(0.6, 0.6, 0.6))
                c.drawCentredString(x + size / 2, y + size / 2 - font_size * 0.35, code)
    c.showPage()


def draw_legend(c, grid, title, shape):
    counts = Counter(code for row in grid for code in row)
    used = [p for p in PALETTE if counts[p[0]]]
    _black_page(c)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(MARGIN + 0.3 * INCH, PAGE_H - MARGIN - 0.5 * INCH, title)
    c.setFont("Helvetica", 11)
    c.setFillColor(Color(0.7, 0.7, 0.7))
    c.drawString(MARGIN + 0.3 * INCH, PAGE_H - MARGIN - 0.8 * INCH,
                 f"{len(used)} colours  ·  {sum(counts.values())} cells")

    sw = 0.42 * INCH
    y = PAGE_H - MARGIN - 1.5 * INCH
    for code, name, _ in used:
        x = MARGIN + 0.3 * INCH
        c.setFillColorRGB(1, 1, 1)
        if shape == "circle":
            c.circle(x + sw / 2, y + sw / 2, sw / 2, stroke=0, fill=1)
        else:
            c.roundRect(x, y, sw, sw, sw * 0.18, stroke=0, fill=1)
        c.setFillColor(Color(0.45, 0.45, 0.45))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(x + sw / 2, y + sw / 2 - 6, code)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica", 14)
        c.drawString(x + sw + 0.25 * INCH, y + sw / 2 - 5, name)
        c.setFillColor(Color(0.6, 0.6, 0.6))
        c.setFont("Helvetica", 11)
        c.drawRightString(x + 4.2 * INCH, y + sw / 2 - 4, f"{counts[code]}")
        y -= sw + 0.14 * INCH
    if counts[WHITE_CODE]:
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(Color(0.7, 0.7, 0.7))
        c.drawString(MARGIN + 0.3 * INCH, MARGIN + 0.2 * INCH, "Cells marked W stay white - do not colour them.")
    c.showPage()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--out", default="page.pdf")
    ap.add_argument("--title", default="Untitled")
    ap.add_argument("--cols", type=int, default=40)
    ap.add_argument("--rows", type=int, default=54)
    ap.add_argument("--shape", choices=["square", "circle"], default="square")
    ap.add_argument("--hex", action="store_true", help="offset odd rows (honeycomb dots)")
    ap.add_argument("--max-colors", type=int, default=15)
    a = ap.parse_args()

    grid, info = convert(a.image, a.cols, a.rows, a.max_colors)
    c = canvas.Canvas(a.out, pagesize=(PAGE_W, PAGE_H))
    c.setTitle(a.title)
    draw_legend(c, grid, a.title, a.shape)
    draw_grid(c, grid, a.shape, a.hex, filled=False)
    draw_grid(c, grid, a.shape, a.hex, filled=True)
    c.save()
    print(f"{a.out}: {a.cols}x{a.rows}, {len({x for r in grid for x in r})} colours, {info}")


if __name__ == "__main__":
    main()
