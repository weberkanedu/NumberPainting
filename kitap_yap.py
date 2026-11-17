"""Folder of images -> full colour-by-number book interior PDF + HTML quality report.

  python kitap_yap.py girdi/ -o cikti/ --book-title "Pixel Color by Number" [--shape circle --hex] [--sort]

Picture titles come from file names: "012_sleepy_cat.png" -> "Sleepy Cat".
Images can be AI renders, flat art or photos; photos are detected and cleaned automatically.
"""
import argparse
import base64
import html
import io
import re
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

import pixelbook as pb

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
INCH, W, H, M = pb.INCH, pb.PAGE_W, pb.PAGE_H, pb.MARGIN
GREY = Color(0.7, 0.7, 0.7)


class Book:
    """Canvas wrapper that counts pages so picture spreads always start on a left (even) page."""

    def __init__(self, path, title):
        self.c = canvas.Canvas(str(path), pagesize=(W, H))
        self.c.setTitle(title)
        self.pages = 0

    def end_page(self):
        self.c.showPage()
        self.pages += 1

    def blank(self):
        pb._black_page(self.c)
        self.end_page()


SMALL_WORDS = {"a", "an", "the", "of", "on", "in", "at", "by", "to", "and", "or", "with", "for", "from", "over",
               "under", "into", "among", "mid"}


def title_from(path):
    """'021_a_vase_of_pink_peonies' -> 'Vase of Pink Peonies' (book-style title case, no leading article)."""
    words = re.sub(r"^k?\d+[\s_-]*", "", path.stem).replace("_", " ").replace("-", " ").split()
    if len(words) > 1 and words[0].lower() in {"a", "an", "the"}:
        words = words[1:]
    titled = [w if i and w.lower() in SMALL_WORDS else w[:1].upper() + w[1:] for i, w in enumerate(words)]
    return " ".join(titled) or path.stem


assert title_from(Path("021_a_vase_of_pink_peonies_on_a_table.png")) == "Vase of Pink Peonies on a Table"
assert title_from(Path("101_tatil.jpg")) == "Tatil" == title_from(Path("k007_tatil.jpg"))


def grid_image(grid, px=8, gray=False):
    rows, cols = len(grid), len(grid[0])
    img = Image.new("RGB", (cols, rows))
    img.putdata([pb._RGB[x] for row in grid for x in row])
    if gray:
        img = img.convert("L")
    return img.resize((cols * px, rows * px), Image.Resampling.NEAREST)


def count_regions(grid):
    """Number of 4-connected same-code areas: a rough measure of how fiddly a page is."""
    rows, cols = len(grid), len(grid[0])
    seen = [[False] * cols for _ in range(rows)]
    n = 0
    for r in range(rows):
        for c in range(cols):
            if seen[r][c]:
                continue
            n += 1
            stack, code = [(r, c)], grid[r][c]
            seen[r][c] = True
            while stack:
                y, x = stack.pop()
                for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= yy < rows and 0 <= xx < cols and not seen[yy][xx] and grid[yy][xx] == code:
                        seen[yy][xx] = True
                        stack.append((yy, xx))
    return n


def difficulty(colors, regions):
    # shortcut: thresholds picked from a handful of test images, retune after the first real batch.
    score = colors + regions / 25
    return "Easy" if score < 14 else "Medium" if score < 22 else "Hard"


def text_page(book, heading, lines):
    c = book.c
    pb._black_page(c)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(W / 2, H - M - 1.2 * INCH, heading)
    c.setFont("Helvetica", 13)
    c.setFillColor(GREY)
    y = H - M - 2 * INCH
    for line in lines:
        c.drawCentredString(W / 2, y, line)
        y -= 22
    book.end_page()


def palette_page(book):
    c = book.c
    pb._black_page(c)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W / 2, H - M - 0.6 * INCH, "MY PALETTE")
    colors = [p for p in pb.PALETTE if p[0] != pb.WHITE_CODE]
    per_row, cell = 5, 0.32 * INCH
    block_w = (W - 2 * M) / per_row
    for i, (code, name, _) in enumerate(colors):
        bx = M + (i % per_row) * block_w + (block_w - 3 * cell) / 2
        by = H - M - 1.4 * INCH - (i // per_row) * 1.65 * INCH
        for j in range(9):  # 3x3 test swatch, code in the centre
            x, y = bx + (j % 3) * cell, by - (j // 3) * cell
            c.setFillColorRGB(1, 1, 1)
            c.roundRect(x + 2, y + 2, cell - 4, cell - 4, 3, stroke=0, fill=1)
            if j == 4:
                c.setFillColor(Color(0.45, 0.45, 0.45))
                c.setFont("Helvetica-Bold", 11)
                c.drawCentredString(x + cell / 2, y + cell / 2 - 4, code)
        c.setFillColor(GREY)
        c.setFont("Helvetica", 9)
        c.drawCentredString(bx + 1.5 * cell, by - 2 * cell - 12, name)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(W / 2, M + 0.3 * INCH, "Test each marker in the empty squares around its code. W cells are never coloured.")
    book.end_page()


def thumb_pages(book, items, heading, per_row, per_col, gray, checkbox):
    """Pages of small previews with number + title (contents page or answer keys)."""
    tw = (W - 2 * M) / per_row
    th = (H - 2 * M - 0.6 * INCH) / per_col
    per_page = per_row * per_col
    for start in range(0, len(items), per_page):
        c = book.c
        pb._black_page(c)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(W / 2, H - M - 0.3 * INCH, heading)
        for k, it in enumerate(items[start:start + per_page]):
            img = grid_image(it["grid"], px=4, gray=gray)
            iw = tw - 0.15 * INCH
            ih = min(th - 0.35 * INCH, iw * img.height / img.width)
            iw = ih * img.width / img.height
            x = M + (k % per_row) * tw + (tw - iw) / 2
            y = H - M - 0.6 * INCH - (k // per_row + 1) * th + 0.3 * INCH
            c.drawImage(ImageReader(img), x, y, iw, ih)
            label = f"{it['num']}  {it['title']}"[:26]
            c.setFont("Helvetica", 7)
            c.setFillColor(GREY)
            if checkbox:
                c.setStrokeColor(GREY)
                c.rect(x, y - 0.17 * INCH, 7, 7, stroke=1, fill=0)
                c.drawString(x + 11, y - 0.16 * INCH, label)
            else:
                c.drawString(x, y - 0.16 * INCH, label)
        book.end_page()


def write_report(items, path):
    rows = []
    for it in items:
        buf = io.BytesIO()
        grid_image(it["grid"], px=3).save(buf, "PNG")
        src = base64.b64encode(buf.getvalue()).decode()
        warn = "<br>".join(html.escape(w) for w in it["warnings"]) or "—"
        rows.append(
            f"<tr class='{'warn' if it['warnings'] else ''}'><td>{it['num']}</td>"
            f"<td><img src='data:image/png;base64,{src}'></td>"
            f"<td><b>{html.escape(it['title'])}</b><br><small>{html.escape(it['file'])}</small></td>"
            f"<td>{'Foto' if it['info']['photo'] else 'Düz çizim'}"
            + (f"<br><small>birleştirilen: {', '.join(it['info']['dropped'])}</small>" if it['info']['dropped'] else "")
            + f"</td><td>{it['colors']}</td>"
            f"<td>{it['regions']}</td><td>{it['white_pct']}%</td><td>{it['difficulty']}</td><td>{warn}</td></tr>")
    n_warn = sum(1 for it in items if it["warnings"])
    path.write_text(f"""<!doctype html><meta charset=utf-8><title>Kalite raporu</title>
<style>body{{font:14px system-ui;margin:24px;background:#fff;color:#222}}table{{border-collapse:collapse}}
td,th{{border-bottom:1px solid #ddd;padding:6px 10px;text-align:left;vertical-align:middle}}
tr.warn{{background:#fff4e0}}img{{image-rendering:pixelated;display:block}}</style>
<h1>Kalite raporu</h1><p>{len(items)} resim · {n_warn} uyarılı</p>
<table><tr><th>#</th><th>Önizleme</th><th>Başlık</th><th>Tür</th><th>Renk</th><th>Bölge</th><th>Beyaz</th><th>Zorluk</th><th>Uyarı</th></tr>
{''.join(rows)}</table>""", encoding="utf-8")


def analyse(path, num, cols, rows, max_colors):
    grid, info = pb.convert(path, cols, rows, max_colors)
    cells = cols * rows
    codes = [x for row in grid for x in row]
    colors = len(set(codes))
    regions = count_regions(grid)
    white_pct = round(100 * codes.count(pb.WHITE_CODE) / cells)
    warnings = []
    if colors < 5:
        warnings.append(f"Sadece {colors} renk: sıkıcı olabilir")
    if white_pct > 35:
        warnings.append(f"Hücrelerin %{white_pct}'i beyaz: boyanacak alan az")
    if regions > cells * 0.25:
        warnings.append(f"Çok dağınık ({regions} bölge): görsel karmaşık, daha sade kaynak dene")
    if info["cleaned"] > cells * 0.05:
        warnings.append(f"{info['cleaned']} gürültü hücresi temizlendi")
    return {"num": num, "file": path.name, "title": title_from(path), "grid": grid, "info": info,
            "colors": colors, "regions": regions, "white_pct": white_pct,
            "difficulty": difficulty(colors, regions), "warnings": warnings}


def build_book(input_dir, out_dir, book_title="Pixel Color by Number", cols=40, rows=54, max_colors=15,
               shape="square", hex_offset=False, sort=False, log=print, progress=None):
    """Returns (pdf_path, report_path). Raises ValueError if the folder has no images.
    progress(done, total): optional callback; analysis is ~90% of the work, PDF writing the rest."""
    input_dir, out_dir = Path(input_dir), Path(out_dir)
    files = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in IMAGE_EXT)
    if not files:
        raise ValueError(f"{input_dir} klasöründe görsel yok")
    out_dir.mkdir(parents=True, exist_ok=True)

    items = []
    for i, f in enumerate(files, 1):
        if progress:
            progress(i - 1, len(files) + 1)
        it = analyse(f, i, cols, rows, max_colors)
        items.append(it)
        log(f"[{i}/{len(files)}] {f.name}: {it['colors']} renk, {it['difficulty']}"
            + (" (foto)" if it["info"]["photo"] else "") + (" [UYARI]" if it["warnings"] else ""))
    if sort:
        order = {"Easy": 0, "Medium": 1, "Hard": 2}
        items.sort(key=lambda it: (order[it["difficulty"]], it["regions"]))
        for n, it in enumerate(items, 1):
            it["num"] = n

    if progress:
        progress(len(files), len(files) + 1)
    pdf_path, report_path = out_dir / "kitap_ic_sayfalar.pdf", out_dir / "rapor.html"
    book = Book(pdf_path, book_title)
    text_page(book, book_title, [f"{len(items)} pixel pictures to colour by code"])
    text_page(book, "How to colour", [
        "1. Test your markers on the palette page and note which marker matches each code.",
        "2. Each picture has a key on the left page: the codes it uses and how many cells.",
        "3. Colour every cell with the colour of its code. Cells marked W stay white.",
        "4. Work one colour at a time - it is faster and you will make fewer mistakes.",
        "5. Alcohol markers bleed: slip a sheet of paper behind the page you colour.",
        "6. Tick the box on the contents page when a picture is done.",
    ])
    palette_page(book)
    thumb_pages(book, items, "CONTENTS", 6, 5, gray=True, checkbox=True)
    for it in items:
        if book.pages % 2 == 0:  # next page would be odd (right); legend must sit on the left
            book.blank()
        pb.draw_legend(book.c, it["grid"], f"{it['num']}. {it['title']}", shape)
        pb.draw_grid(book.c, it["grid"], shape, hex_offset, filled=False)
        book.pages += 2
    thumb_pages(book, items, "ANSWER KEYS", 4, 3, gray=False, checkbox=False)
    book.c.save()
    write_report(items, report_path)
    log(f"Bitti: {book.pages} sayfa, {sum(1 for it in items if it['warnings'])} uyarılı resim")
    return pdf_path, report_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("cikti"))
    ap.add_argument("--book-title", default="Pixel Color by Number")
    ap.add_argument("--cols", type=int, default=40)
    ap.add_argument("--rows", type=int, default=54)
    ap.add_argument("--max-colors", type=int, default=15)
    ap.add_argument("--shape", choices=["square", "circle"], default="square")
    ap.add_argument("--hex", action="store_true")
    ap.add_argument("--sort", action="store_true", help="order pictures from easy to hard")
    a = ap.parse_args()
    try:
        build_book(a.input, a.out, a.book_title, a.cols, a.rows, a.max_colors, a.shape, a.hex, a.sort)
    except ValueError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
