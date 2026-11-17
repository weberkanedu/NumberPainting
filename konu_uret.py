"""Endless supply of fresh, simple, VARIED colouring-page topics.

Every topic is ONE clear subject (those read well on a 40x54 grid, busy scenes do not).
Variety rules:
  - every subject has a key (canary, succulent, lighthouse...): a key is used once; a second canary on
    another branch is not a new picture. Only after every key is used do variants (new vase/branch/colours)
    of used keys appear.
  - topics rotate through many families (flowers, birds, sea life, food, music, vehicles...), so the four
    pictures of one 2x2 sheet come from four different families.
"""
import csv
import random
import re

AUTO = "oto-"  # category prefix of generated rows; "refresh" only ever replaces these

VESSELS = ["a white ceramic vase", "a terracotta pot", "a blue and white porcelain vase", "a glass bottle",
           "a copper jug", "a woven basket", "an enamel watering can", "a teacup", "a stoneware jar",
           "a brass pot", "a green glass vase", "a striped ceramic pot", "a mason jar"]
PERCHES = ["a flowering branch", "a mossy twig", "an olive branch", "a birch twig", "a pine branch", "a wooden post"]
MOODS = ["in warm autumn colours", "in cool moonlight blues", "in soft pastel colours", "in rich jewel tones",
         "in golden sunset colours", "in fresh spring colours", "in deep forest greens", "in candy colours"]

# family -> [(key, subject)]; {vessel}/{perch} are filled at random. The key must appear in the subject.
FAMILIES = {
    "flowers": [(k, f"{p} in {{vessel}}") for k, p in [
        ("peony", "pink peonies"), ("rose", "red roses"), ("tulip", "tulips"), ("sunflower", "sunflowers"),
        ("orchid", "an orchid"), ("hydrangea", "blue hydrangeas"), ("daisy", "daisies"), ("lavender", "lavender"),
        ("poppy", "red poppies"), ("iris", "irises"), ("dahlia", "dahlias"), ("magnolia", "magnolia branches"),
        ("anemone", "anemones"), ("ranunculus", "ranunculus"), ("carnation", "carnations"),
        ("calla lily", "calla lilies"), ("sweet pea", "sweet peas"), ("chrysanthemum", "chrysanthemums"),
        ("zinnia", "zinnias"), ("foxglove", "foxgloves"), ("hyacinth", "hyacinths"), ("cosmos", "cosmos flowers")]],
    "plants": [("succulent", "a succulent in {vessel}"), ("cactus", "a flowering cactus in {vessel}"),
               ("bonsai", "a bonsai tree in a shallow pot"), ("monstera", "a monstera plant in {vessel}"),
               ("fern", "a fern in {vessel}"), ("aloe", "an aloe plant in {vessel}"),
               ("lemon tree", "a small lemon tree in {vessel}"), ("olive tree", "a little olive tree in {vessel}")],
    "fruit": [(f, f"{'an' if f[0] in 'aeiou' else 'a'} {f} branch with ripe fruit and leaves") for f in
              ["lemon", "orange", "cherry", "apple", "pomegranate", "olive", "fig", "peach", "plum", "apricot",
               "quince", "pear", "blackberry", "persimmon"]],
    "birds": [(b, f"{'an' if b[0] in 'aeiou' else 'a'} {b} perched on {{perch}}") for b in
              ["robin", "goldfinch", "kingfisher", "bluebird", "hummingbird", "cardinal", "parrot", "barn owl",
               "blue jay", "swallow", "bee-eater", "toucan", "magpie", "canary", "lovebird", "wren", "hoopoe"]],
    "animals": [("fox", "a red fox sitting"), ("tiger", "a tiger head portrait"), ("lion", "a lion head portrait"),
                ("snow leopard", "a snow leopard lying down"), ("wolf", "a wolf head portrait"),
                ("deer", "a deer with antlers"), ("hare", "a hare sitting upright"), ("raccoon", "a raccoon portrait"),
                ("koala", "a koala hugging a branch"), ("panda", "a panda sitting"), ("zebra", "a zebra head portrait"),
                ("giraffe", "a giraffe head portrait"), ("elephant", "an elephant walking"),
                ("horse", "a horse head portrait"), ("highland cow", "a highland cow portrait"),
                ("polar bear", "a polar bear"), ("penguin", "a penguin standing"), ("swan", "a swan on water"),
                ("flamingo", "a flamingo standing"), ("peacock", "a peacock with open tail"),
                ("chameleon", "a chameleon on a branch"), ("frog", "a frog on a lily pad"),
                ("squirrel", "a squirrel holding an acorn"), ("hedgehog", "a hedgehog"), ("otter", "an otter floating"),
                ("capybara", "a capybara sitting"), ("sloth", "a sloth hanging from a branch"),
                ("red panda", "a red panda on a branch"), ("llama", "a llama portrait")],
    "pets": [("cat", "a tabby cat curled up asleep"), ("siamese", "a siamese cat sitting"),
             ("golden retriever", "a golden retriever portrait"), ("dachshund", "a dachshund sitting"),
             ("corgi", "a corgi sitting"), ("pug", "a pug portrait"), ("rabbit", "a lop-eared rabbit"),
             ("parakeet", "a parakeet on a perch"), ("goldfish", "a fancy goldfish"), ("husky", "a husky portrait")],
    "sea": [("sea turtle", "a sea turtle swimming"), ("koi", "a koi fish"), ("octopus", "an octopus"),
            ("jellyfish", "a jellyfish"), ("seahorse", "a seahorse"), ("whale", "a humpback whale tail above water"),
            ("dolphin", "a leaping dolphin"), ("clownfish", "a clownfish"), ("starfish", "a starfish"),
            ("nautilus", "a nautilus shell"), ("crab", "a red crab"), ("manta ray", "a manta ray")],
    "insects": [("monarch", "a monarch butterfly with open wings"), ("blue morpho", "a blue morpho butterfly"),
                ("swallowtail", "a swallowtail butterfly"), ("luna moth", "a luna moth"),
                ("atlas moth", "an atlas moth"), ("dragonfly", "a dragonfly"), ("ladybug", "a ladybug on a leaf"),
                ("bee", "a honey bee on a flower"), ("stag beetle", "a stag beetle"), ("snail", "a snail with a spiral shell")],
    "food": [("cupcake", "a cupcake"), ("layer cake", "a slice of layer cake"), ("croissant", "a croissant"),
             ("macaron", "a stack of macarons"), ("sundae", "an ice cream sundae"), ("pineapple", "a pineapple"),
             ("watermelon", "a watermelon slice"), ("grape", "a bunch of grapes"), ("strawberry", "a strawberry"),
             ("donut", "a glazed donut"), ("cherry pie", "a cherry pie"), ("sushi", "a sushi roll"),
             ("pancake", "a stack of pancakes"), ("avocado", "an avocado cut in half")],
    "drinks": [("wine", "a glass of red wine"), ("cocktail", "a cocktail with a lemon twist"),
               ("tea glass", "a Turkish tea glass on a saucer"), ("turkish coffee", "a Turkish coffee cup"),
               ("latte", "a latte with heart foam art"), ("milkshake", "a strawberry milkshake"),
               ("lemonade", "a jar of lemonade"), ("teapot", "a vintage teapot")],
    "vintage": [("lantern", "an oil lantern"), ("hourglass", "an hourglass"), ("compass", "a brass compass"),
                ("pocket watch", "a pocket watch"), ("camera", "a vintage camera"), ("gramophone", "a gramophone"),
                ("typewriter", "a typewriter"), ("perfume", "a perfume bottle"), ("telephone", "a rotary telephone"),
                ("radio", "a vintage radio"), ("key", "an ornate old key"), ("candle", "a candle in a holder")],
    "music": [("guitar", "an acoustic guitar"), ("violin", "a violin"), ("trumpet", "a trumpet"),
              ("saxophone", "a saxophone"), ("drum", "a drum"), ("vinyl", "a vinyl record"), ("harp", "a harp"),
              ("oud", "an oud"), ("headphones", "a pair of headphones")],
    "travel": [("hot air balloon", "a hot air balloon"), ("lighthouse", "a lighthouse"), ("sailboat", "a sailboat"),
               ("windmill", "a windmill"), ("scooter", "a classic scooter"), ("bicycle", "a vintage bicycle"),
               ("vintage car", "a vintage car"), ("locomotive", "a steam locomotive"), ("tram", "a red tram"),
               ("camper van", "a camper van"), ("suitcase", "a vintage suitcase with stickers")],
    "space": [("crescent moon", "a crescent moon"), ("planet", "a ringed planet"), ("rocket", "a vintage rocket"),
              ("astronaut", "an astronaut helmet"), ("sun", "a radiant sun with long rays"), ("comet", "a comet"),
              ("crystal", "an amethyst crystal cluster"), ("crystal ball", "a crystal ball on a stand")],
    "nature": [("mushroom", "a red mushroom"), ("pine cone", "a pine cone"), ("acorn", "an acorn with oak leaves"),
               ("feather", "a peacock feather"), ("maple leaf", "an autumn maple leaf"), ("snowflake", "a snowflake"),
               ("seashell", "a scallop seashell"), ("rainbow", "a rainbow with clouds")],
    "fantasy": [("dragon", "a small dragon"), ("unicorn", "a unicorn head"), ("phoenix", "a phoenix"),
                ("mermaid", "a mermaid tail splashing"), ("fairy house", "a mushroom fairy house"),
                ("griffin", "a griffin"), ("crown", "a jewelled crown"), ("magic potion", "a magic potion bottle")],
    "turkish": [("evil eye", "an evil eye bead"), ("simit", "a simit"), ("cezve", "a copper cezve"),
                ("turkish delight", "a plate of Turkish delight"), ("mosaic lamp", "a colourful mosaic lamp"),
                ("tulip vase", "an Ottoman tulip vase"), ("baklava", "a tray of baklava")],
}


def _matches(key, subject):
    """Whole-word match of a key, singular or plural (canary/canaries, peony/peonies, fox/foxes)."""
    forms = {key, key + "s", key + "es"} | ({key[:-1] + "ies"} if key.endswith("y") else set())
    return any(re.search(rf"\b{re.escape(f)}\b", subject.lower()) for f in forms)


def _fill(template, rng):
    return template.format(vessel=rng.choice(VESSELS), perch=rng.choice(PERCHES))


def base_of(subject):
    """The subject without its colour mood."""
    for m in MOODS:
        if subject.lower().endswith(" " + m.lower()):
            return subject[:-len(m) - 1]
    return subject


def generate(n, existing_subjects, rng=None):
    """n new (subject, category) pairs, families interleaved, keys not reused while unused keys remain."""
    rng = rng or random.Random()
    existing = [s.lower() for s in existing_subjects]
    taken_full = set(existing)
    used_keys = {k for items in FAMILIES.values() for k, _ in items if any(_matches(k, s) for s in existing)}
    fresh, variants = {}, {}
    for fam, items in FAMILIES.items():
        for key, template in items:
            (variants if key in used_keys else fresh).setdefault(fam, []).append((key, template))
    # families of the last 3 existing topics, so a new batch doesn't continue a family across the seam
    recent = [fam for s in existing[-3:] for fam, items in FAMILIES.items() if any(_matches(k, s) for k, _ in items)][-3:]
    out, out_keys, counts = [], set(), {fam: 0 for fam in FAMILIES}
    for tier in (fresh, variants):
        for items in tier.values():
            rng.shuffle(items)
        while len(out) < n:
            avail = [f for f in tier if tier[f]]
            if not avail:
                break
            # sliding window: never a family used in the previous 3 topics (so any 4 in a row differ),
            # and among the rest the least-used family, so the book stays balanced
            last3 = (recent + [c for _, c in out])[-3:]
            pool = [f for f in avail if f not in last3] or avail
            low = min(counts[f] for f in pool)
            fam = rng.choice([f for f in pool if counts[f] == low])
            key, template = tier[fam].pop()
            if key in out_keys:
                continue
            for _ in range(12):  # variants need a vase/branch/mood combination not used yet
                s = _fill(template, rng)
                if tier is variants or rng.random() < 0.5:
                    s = f"{s} {rng.choice(MOODS)}"
                if s.lower() not in taken_full:
                    break
            else:
                continue
            taken_full.add(s.lower())
            out_keys.add(key)
            counts[fam] += 1
            out.append((s, fam))
    return out


def read_rows(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("subject", "").strip()]


def write_rows(csv_path, rows):
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["no", "subject", "category"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def add_topics(csv_path, n, rng=None):
    """Append n fresh generated topics to the CSV. Returns how many were added."""
    rows = read_rows(csv_path)
    nxt = max((int(r["no"]) for r in rows), default=0) + 1
    new = generate(n, [r["subject"] for r in rows], rng)
    rows += [{"no": nxt + i, "subject": s, "category": AUTO + c} for i, (s, c) in enumerate(new)]
    write_rows(csv_path, rows)
    return len(new)


def refresh_pending(csv_path, is_done, n, rng=None):
    """Replace generated topics that have no image yet with n new ones (user-written rows are kept)."""
    rows = read_rows(csv_path)
    keep = [r for r in rows if is_done(r) or not r.get("category", "").startswith(AUTO)]
    used = [r["subject"] for r in rows]  # also skip the ones being thrown away, so they don't come straight back
    nxt = max((int(r["no"]) for r in rows), default=0) + 1
    new = generate(n, used, rng)
    write_rows(csv_path, keep + [{"no": nxt + i, "subject": s, "category": AUTO + c} for i, (s, c) in enumerate(new)])
    return len(new)


if __name__ == "__main__":  # self-check
    for fam, items in FAMILIES.items():
        for key, template in items:
            assert _matches(key, template), (fam, key, template)  # every key is findable in its own subject
    keys = sum(len(v) for v in FAMILIES.values())
    r = random.Random(1)
    first = generate(40, [], r)
    fams = [c for _, c in first]
    assert len(first) == 40 and all(len(set(fams[i:i + 4])) == 4 for i in range(0, 40, 4)), "a sheet repeats a family"
    used = []
    while len(used) < keys + 120:  # batches of 40 well past the key pool: never an exact repeat
        batch = generate(40, used, r)
        assert len(batch) == 40
        used += [s for s, _ in batch]
    assert len({s.lower() for s in used}) == len(used)
    first_keys = [k for s in used[:keys] for items in FAMILIES.values() for k, _ in items if _matches(k, s)]
    assert len(set(first_keys)) >= keys - 5, "keys repeated before the pool was used up"
    print(f"{len(FAMILIES)} families, {keys} unique subjects; first sheet-sized groups:")
    for i in range(0, 12, 4):
        print("  " + " | ".join(f"[{c}] {s}" for s, c in first[i:i + 4]))
