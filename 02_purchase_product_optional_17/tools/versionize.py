#!/usr/bin/env python3
"""Turn the published Odoo 17.0 listing into the 16.0 / 18.0 / 19.0 listings.

    python3 versionize.py index.html 16 out_16.html

Two kinds of edit happen here.

1. VERSION SWAPS -- text that names the Odoo series, the build number and the
   cross-sell links. Mechanical.

2. NEUTRALISED CLAIMS -- the 17.0 copy carries counts that were measured by
   reading that build's source: the dependency list
   (purchase_product_matrix / sale_product_configurator), 42 translation files,
   5 Python test modules + 2 QUnit files + 1 browser tour, ~1,500 lines of code.
   None of that is verifiable for another series -- the store publishes this
   module for 16.0 and 17.0 only, no source tree for 16/18/19 is in the repo,
   and Odoo 18 reworked the product configurator, so the dependency list almost
   certainly differs. Rather than restate 17's numbers on a page selling a
   different build, every count becomes a qualitative claim that stays true.
   Same reason the browser-chrome labels lose "Odoo 17.0": the screenshots and
   the hero GIF are Odoo 17 captures.

Every replacement is asserted, so a phrase that stops matching after an edit to
the 17.0 listing fails the build instead of silently vanishing.
"""
import re
import sys

SRC, SERIES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
N = SERIES  # "16" | "18" | "19"

raw = open(SRC, encoding="utf-8").read()
applied, missed = [], []


def sub(literal, replacement, count=0, label=None):
    """Replace `literal` allowing any whitespace where it has spaces, because
    the file is Prettier-wrapped and a phrase can straddle a line break."""
    global raw
    pattern = r"\s+".join(re.escape(w) for w in literal.split(" "))
    raw, n = re.subn(pattern, replacement.replace("\\", "\\\\"), raw,
                     count=count)
    (applied if n else missed).append("%-58s x%d" % (label or literal[:56], n))
    return n


# ---------------------------------------------------------------- 1. versions
sub("for Odoo 17 purchase orders", "for Odoo %s purchase orders" % N)
sub("Free Odoo 17 module.", "Free Odoo %s module." % N)
# the eyebrow is mixed case in the source and uppercased by CSS
sub("Free module &middot; Odoo 17 &middot; Purchase",
    "Free module &middot; Odoo %s &middot; Purchase" % N, label="hero eyebrow")
sub("Odoo 17.0 &middot; Community or Enterprise",
    "Odoo %s.0 &middot; Community or Enterprise" % N)
sub("What Odoo 17 does and does not give Purchase",
    "What Odoo %s does and does not give Purchase" % N)
sub("Standard Odoo 17 purchase order", "Standard Odoo %s purchase order" % N)
sub("Four kinds of Odoo 17 team we built this around",
    "Four kinds of Odoo %s team we built this around" % N)
sub("Odoo 17 teams whose buyers configure products",
    "Odoo %s teams whose buyers configure products" % N)
sub("Odoo 17.0, Community or Enterprise. This listing is the 17.0 build;",
    "Odoo %s.0, Community or Enterprise. This listing is the %s.0 build;" % (N, N))
sub("17.0.1.0.0", "%s.0.1.0.0" % N)
sub("Current release &middot; Odoo 17.0", "Current release &middot; Odoo %s.0" % N)

# the FAQ answer names the series and used to promise an Odoo 18 port, which
# reads as nonsense on the 18.0 and 19.0 pages
sub("Odoo 17.0. That is what this build is and that is all we claim. "
    "A port to Odoo 18 is in development; when it is released it gets its own "
    "listing and its own version number, not a quiet edit to this page.",
    "Odoo %s.0. That is what this build is and that is all we claim. Every "
    "other series gets its own listing and its own version number, not a quiet "
    "edit to this page." % N,
    label="FAQ: which Odoo versions")

sub("Next up, honestly labelled: an Odoo 18 port is in development, and we are "
    "reviewing how the order's currency is passed to the price conversion",
    "Next up, honestly labelled: we are reviewing how the order's currency is "
    "passed to the price conversion",
    label="roadmap: drop the 18 port line")
sub("Both will appear here as versions when they ship, not as promises before.",
    "It will appear here as a version when it ships, not as a promise before.",
    label="roadmap: singular")

# ------------------------------------------------- 2. screenshots are Odoo 17
for doc in ("Purchase / Purchase Orders / P00042",
            "Purchase / Requests for Quotation / New",
            "Product / Conference Chair / Purchase",
            "Purchase / Requests for Quotation / P00014"):
    sub("%s &nbsp;&mdash;&nbsp; Odoo 17.0" % doc, doc,
        label="frame label: %s" % doc[:34])

sub("Configuring a Conference Chair on an Odoo 17 purchase order",
    "Configuring a Conference Chair on a purchase order", label="alt: hero GIF")
sub("The Odoo 17 product configurator open on a purchase order line",
    "The Odoo product configurator open on a purchase order line",
    label="alt: feature 01")

# ------------------------------------------------- 3. unverifiable dependencies
sub("Purchase, plus two standard Odoo modules: <b>purchase_product_matrix</b> "
    "and <b>sale_product_configurator</b>. Odoo installs both for you.",
    "Purchase, plus the standard Odoo modules this build depends on. Odoo "
    "installs them for you.", label="reqs card: other apps needed")
sub("It depends on Purchase, <b>purchase_product_matrix</b> and "
    "<b>sale_product_configurator</b>, all of which come with standard Odoo.",
    "It depends on Purchase and the standard Odoo modules that ship with it.",
    label="FAQ: depends on")

# ------------------------------------------------------ 4. translation counts
sub("42 translation files", "Translation files", label="chip / bullets")


# ------------------------------------------------------------- 5. test counts
sub("5 Python test modules, 2 QUnit component test files and 1 browser tour, "
    "all inside the download", "Python test modules, QUnit component test files "
    "and a browser tour, all inside the download", label="download table: tests")
sub("Included, not hidden: 5 Python test modules, 2 QUnit files and a browser "
    "tour.", "Included, not hidden: Python test modules, QUnit files and a "
    "browser tour.", label="reqs card: tests")
sub("Test suite shipped with the module: 5 Python test modules, 2 QUnit files, "
    "1 browser tour.", "Test suite shipped with the module: Python tests, QUnit "
    "component tests and a browser tour.", label="release bullet: tests")

# ------------------------------------------------------------ 6. lines of code
sub("LGPL-3. Around 1,500 lines of Python and JavaScript, no obfuscation, no "
    "licence server, no phone-home.",
    "LGPL-3. Python and JavaScript you can read, no obfuscation, no licence "
    "server, no phone-home.", label="download table: source")

# -------------------------------------------------------------- 7. stat band
# the band's whole point was countable numbers; without them the tiles state
# what is still provable
sub("Every number here is countable inside the download.",
    "Everything here is checkable inside the download.", label="stat band lede")
TILE = re.compile(
    r'(<div\s+class="ppint-n"[^>]*>)(\s*)([^<]{1,14}?)(\s*)'
    r'(</div\s*>\s*<div\s+class="ppint-l"[^>]*>)(\s*)(.*?)(\s*)(</div\s*>)', re.S)
TILE_NEW = {
    "translation files in <i>i18n</i>": ("i18n", "translation files in the download"),
    "test files: 5 Python, 2 QUnit, 1 tour": ("Tests", "Python, QUnit and a browser tour"),
    "dependencies, all standard Odoo": ("LGPL-3", "source you can read"),
}
_tiles = []


def _tile(m):
    label = " ".join(m.group(7).split())
    if label not in TILE_NEW:
        return m.group(0)
    value, newlabel = TILE_NEW[label]
    _tiles.append(label)
    return (m.group(1) + m.group(2) + value + m.group(4) + m.group(5)
            + m.group(6) + newlabel + m.group(8) + m.group(9))


raw = TILE.sub(_tile, raw)
applied.append("%-58s x%d" % ("stat tiles rewritten", len(_tiles)))
# tile 4 kept "$0 / LGPL-3, source included", which now repeats tile 3
sub("LGPL-3, source included", "no subscription, no per-user fee",
    label="stat tile 4 label")
for _t in TILE_NEW:
    if _t not in _tiles:
        missed.append("%-58s x0" % ("stat tile: " + _t[:44]))

# --------------------------------------------------------- 8. cross-sell links
n = len(re.findall(r'/apps/modules/17\.0/', raw))
raw = raw.replace("/apps/modules/17.0/", "/apps/modules/%s.0/" % N)
applied.append("%-58s x%d" % ("cross-sell hrefs -> /apps/modules/%s.0/" % N, n))

# the header's provenance paragraph cited 17.0's own counts
sub("EVERY factual claim on this page is sourced from the module itself: "
    "__manifest__.py, models/, controllers/main.py, static/src/js/, "
    "views/purchase_order_views.xml, i18n/ (42 .po files), tests/ (5 Python "
    "test modules) and static/tests/ (2 QUnit files + 1 tour). Nothing is "
    "estimated.",
    "EVERY factual claim on this page is sourced from the module itself: "
    "__manifest__.py, models/, controllers/main.py, static/src/js/, "
    "views/purchase_order_views.xml, i18n/, tests/ and static/tests/. The "
    "counts that were measured on the 17.0 tree are stated qualitatively here, "
    "because this series has no source tree in the repo to measure.",
    label="header: provenance paragraph")

# ------------------------------------------------------------- 9. header note
sub("Odoo 17.0 &middot; module version",
    "Odoo %s.0 &middot; module version" % N, label="header: series line")
raw = raw.replace(
    "  PASTE TARGET:",
    "  GENERATED from the published 17.0 listing by tools/versionize.py.\n"
    "  Version-bound claims are deliberately neutralised, because no %s.0\n"
    "  source tree exists in this repo to measure them against: the dependency\n"
    "  list, the translation-file count, the test counts and the line count are\n"
    "  all stated qualitatively. The screenshots and the hero GIF are Odoo 17\n"
    "  captures, so the browser-chrome labels no longer print a version number.\n"
    "  Re-check every one of those against the real %s.0 manifest before upload.\n"
    "\n  PASTE TARGET:" % (N, N), 1)

if missed:
    print("  !! %d phrase(s) did not match -- the 17.0 listing changed:" % len(missed))
    for m in missed:
        print("     " + m)
    sys.exit(1)

open(OUT, "w", encoding="utf-8").write(raw)
print("  %s -> %s" % (SRC, OUT))
for a in applied:
    print("     " + a)
