"""Topics (konular.csv) and the Gemini prompts built from them.

A prompt asks either for one picture, or for a 2x2 "sheet" of four pictures that the app
cuts into four topics, so one Gemini round gives four book pages.
"""
import csv
import re

# What reads well on a 40x54 colouring grid: ONE clear subject with a bold silhouette on a plain dark
# background (busy scenes and tiny details turn to noise).
_TECH = (
    "Exactly one subject, LARGE: it fills about 80 to 90 percent of the frame height, centred, with a bold "
    "silhouette that is instantly recognisable even at 40x54 pixels. No busy scene, no clutter, no small "
    "background objects, no scenery. Plain dark charcoal background with at most a few sparkle pixels. "
    "Large square pixels on a grid of about 40 pixels wide and 54 tall, portrait 3:4. Flat solid colours only, "
    "10 to 15 rich colours, no gradients, no anti-aliasing, no blur; shade with pixel dithering. "
    "No text, no letters, no border, no watermark."
)
# Gemini keeps the look of earlier images in the same chat (e.g. after a children's prompt), so every
# prompt states its own style and asks to ignore earlier ones.
_RESET = "Ignore the style of any earlier images in this conversation; use only the style described here. "
STYLE = (_RESET + "Refined, detailed pixel art for an ADULT colouring book, like a fine natural-history or "
         "still-life illustration: realistic proportions, rich detailed shading and texture. NOT cute, NOT chibi, "
         "NOT kawaii, NOT cartoon, NOT sticker or emoji style, no big eyes or smiling faces on animals or objects. "
         + _TECH)
KIDS_STYLE = (_RESET + "Cute, friendly pixel art for a CHILDREN's colouring book: adorable and cheerful with big simple "
              "shapes and bright happy colours. " + _TECH)
SHEET_POSITIONS = ["Top-left", "Top-right", "Bottom-left", "Bottom-right"]
CUSTOM, CUSTOM_KIDS = "ozel", "ozel-cocuk"  # categories of topics typed into the app
RETIRED = "iptal"  # topic whose image the user deleted: never asked for again (still counts as "used")
_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def slug(text, limit=60):
    s = re.sub(r"[^a-z0-9]+", "_", text.translate(_TR).lower()).strip("_")
    # cut on a word boundary: the file name is also the picture's title in the book
    return s if len(s) <= limit else s[:limit + 1].rsplit("_", 1)[0]


def file_name(no, subject):
    return f"{int(no):03d}_{slug(subject)}.png"


def load_topics(csv_path):
    """[(file_name, subject, category), ...] from the topics CSV (columns: no, subject, category)."""
    with open(csv_path, encoding="utf-8-sig") as f:  # -sig: Excel saves CSVs with a BOM
        rows = [r for r in csv.DictReader(f) if r.get("subject", "").strip()]
    return [(file_name(r["no"], r["subject"]), r["subject"].strip(), (r.get("category") or "").strip()) for r in rows]


def single_prompt(subject, kids=False):
    return f"Create an image: pixel art of {subject}. {KIDS_STYLE if kids else STYLE}"


def sheet_prompt(subjects):
    assert len(subjects) == 4
    panels = " ".join(f"{pos}: {s}." for pos, s in zip(SHEET_POSITIONS, subjects))
    return ("Create one portrait 3:4 image made of four separate pictures in a 2x2 grid of equal panels, "
            "split by thin straight black lines. Each panel is its own complete picture of a single LARGE subject "
            "filling its panel, on a plain dark background, and must not spill into the others. "
            f"{panels} Style for every panel: {STYLE}")


assert slug("Gözlüklü kırmızı kapibara İstanbul'da") == "gozluklu_kirmizi_kapibara_istanbul_da"
