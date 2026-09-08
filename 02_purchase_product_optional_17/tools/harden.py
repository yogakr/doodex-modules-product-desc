#!/usr/bin/env python3
"""Rebuild the Purchase Product Optional store listing so it survives the
Odoo Apps Store sanitizer.

The store deletes the <style> block outright and property-filters every inline
style attribute (see store_sim.py for the empirical model). So this script:

  1. resolves the CSS cascade itself and writes the surviving declarations into
     inline style attributes,
  2. translates the declarations the store drops (flex/grid/gap/box-shadow/...)
     into Bootstrap 5 utility classes, which the store page does provide,
  3. replaces CSS-only decoration (::before markers, rotated chevrons) with real
     markup,
  4. stamps width/height on every <img>, because the icons are 3x assets that
     were sized only by a CSS class,
  5. emits a fragment: no <head>, no external font link, no <style>.
"""
import re
import sys
from collections import OrderedDict

import cssselect
from lxml import etree
from lxml import html as LH

from store_sim import STYLE_ALLOWLIST

SRC = sys.argv[1] if len(sys.argv) > 1 else "src.html"
OUT = sys.argv[2] if len(sys.argv) > 2 else "index.hardened.html"

# --------------------------------------------------------------------------
# Bootstrap-5 translation of every layout declaration the store throws away.
# Keyed by the element's own class. (add_classes, drop_display)
# --------------------------------------------------------------------------
FLEX = {
    "ppchiprow":    "flex-wrap",
    "ppband-in":    "align-items-center",
    "pphero-top":   "align-items-center justify-content-center flex-wrap",
    "ppframe-bar":  "align-items-center",
    "ppframe-dots": "flex-shrink-0",
    "ppchg-t":      "flex-column",
    "ppchg-b":      "align-items-start",
    "ppchg-a":      "align-items-start",
    "ppba-item":    "align-items-start",
    "ppflow-top":   "align-items-center",
    "ppshot-bed":   "justify-content-center",
    "ppreq-card":   "align-items-start",
    "ppqr-card":    "flex-column",
    "ppqr-top":     "align-items-center justify-content-between",
    "ppbtn":        "align-items-center",
    "ppslot-tag":   "align-items-center",
}
# grid container -> (container classes, per-child column classes, (gx, gy))
#
# IMPORTANT: the store's Bootstrap build does NOT ship the g-*/gx-*/gy-* gutter
# utilities (probed live: `.g-3` leaves --bs-gutter-x empty), and .row's own
# default gutter is not the spacing this design uses. So every row's spacing is
# written as explicit inline margin/padding, both of which do survive:
#   row   -> margin-left/right: -gx/2, margin-bottom: -gy
#   column-> padding-left/right: gx/2,  padding-bottom: gy
# gx/gy come from the `gap` the original grid rule used.
GRID = {
    # wraps on phones, single line from lg up: the @media rules are gone, so the
    # breakpoint has to live in the class
    "ppnav-in":     ("d-flex align-items-center justify-content-between gap-3 flex-wrap flex-lg-nowrap", None, None),
    "ppchg":        ("row", "col-12 col-md-6 col-lg-3", (14, 14)),
    "ppchg-pair":   ("d-flex flex-column gap-2", None, None),  # no columns: a stacked pair
    "ppba":         ("row", "col-12 col-lg-6", (0, 0)),
    "ppflow":       ("row", "col-12 col-md-6 col-lg-3", (24, 24)),
    "ppcap":        ("row", "col-12 col-lg-6", (44, 0)),
    "ppwho":        ("row", "col-12 col-lg-6", (48, 38)),
    "ppreq":        ("row", "col-12 col-md-6 col-lg-4", (14, 14)),
    "ppint-stats":  ("row", "col-6 col-lg-3", (0, 20)),
    "ppprice":      ("row", None, (0, 0)),      # children sized individually below
    "ppprice-list": ("d-flex flex-column gap-2", None, None),
    "ppqr-grid":    ("row", "col-12 col-lg-4", (14, 14)),
    "ppfaq-list":   ("d-flex flex-column gap-2", None, None),
    "pprel":        (None, None, None),
    "pprel-row":    ("row", None, (24, 24)),
    "pprel-list":   ("list-unstyled d-flex flex-column gap-2", None, None),
    "ppwg-grid":    ("row", None, (18, 18)),    # children already carry col-lg-4
}
# containers whose children are unclassed and must be sized by position
POS_CHILD = {
    "pprel-row": ["col-12 col-lg-3", "col-12 col-lg-9"],
}
# one-off child column widths
CHILD_COL = {
    "ppprice-l": "col-12 col-lg-4",
    "ppprice-r": "col-12 col-lg-8",
}
# flex children that must not shrink
NOSHRINK = {"ppframe-dots", "ppchg-t-ico", "ppqr-ico", "ppreq-ico"}

# box-shadow -> border, because box-shadow is dropped by the store
SHADOW_BORDER = {
    "0 0 0 1px rgba(39,1,64,0.06)": ("1px", "#efe7f5"),
    "0 1px 2px rgba(0,0,0,0.04),0 0 0 1px rgba(39,1,64,0.08)": ("1px", "#eae0f2"),
    "0 4px 14px rgba(39,1,64,0.08),0 0 0 1px rgba(39,1,64,0.06)": ("1px", "#e6daf0"),
    "0 8px 22px rgba(250,114,104,0.32)": (None, None),          # coral CTA: solid fill is enough
    "0 0 0 1.5px #270140": ("1.5px", "#270140"),
    "0 0 0 1.5px #fa7268": ("1.5px", "#fa7268"),
    "0 0 0 2px #fa7268": ("2px", "#fa7268"),
    "0 26px 64px rgba(0,0,0,0.4),0 0 0 1px rgba(250,114,104,0.24)": ("1px", "rgba(250,114,104,0.35)"),
    "none": (None, None),
}

DROP_PROPS = {
    "box-sizing",        # Bootstrap's reboot already sets border-box page-wide
    "cursor", "transition", "scroll-margin-top", "content", "pointer-events",
    "position", "inset", "top", "left", "right", "bottom", "z-index",
    "transform", "aspect-ratio", "overflow", "overflow-x", "overflow-y",
    "overflow-wrap", "text-wrap", "word-break", "gap", "row-gap", "column-gap",
    "align-items", "align-self", "justify-content", "justify-self", "justify-items",
    "flex", "flex-basis", "flex-grow", "flex-shrink", "flex-direction", "flex-wrap",
    "grid-template-columns", "grid-template-rows", "grid-column", "grid-row",
    "grid-auto-flow", "place-items", "list-style", "list-style-type",
    "backdrop-filter", "filter", "box-shadow", "outline", "appearance",
    "-webkit-font-smoothing", "font-feature-settings", "text-rendering",
    "object-fit", "mask", "clip-path", "backface-visibility", "will-change",
}


TITLE = ("Purchase Product Optional &mdash; product configurator for Odoo 17 "
         "purchase orders | Doodex")
DESCRIPTION = ("Free Odoo 17 module. Puts Odoo's product configurator and "
               "optional products on purchase order lines, priced with your "
               "vendor's own supplier rates and converted to the order "
               "currency. LGPL-3, source included, by Doodex.")

# The grid/flex fallback, modelled on the Advanced Sales Analysis listing.
# On the store this whole STYLE element is killed and Bootstrap 5 is already
# live, so it changes nothing there. Its job is to make the file lay out
# correctly when it is opened straight off disk with no stylesheet at all.
# Values and variable names are Bootstrap 5's own, so where Bootstrap IS
# present and this block survives, every declaration resolves to what
# Bootstrap already computed. Only the classes this page uses are covered:
# row, col-6/12, col-md-6, col-lg-3/4/6/8/9, d-flex, flex-wrap, flex-column,
# align-items-start/center, justify-content-between/center, table-responsive.
FALLBACK_CSS = """
.ppo, .ppo *, .ppo *::before, .ppo *::after { box-sizing: border-box; }
.ppo img { max-width: 100%; }
.ppo .row {
  --bs-gutter-x: 1.5rem; --bs-gutter-y: 0;
  display: flex; flex-wrap: wrap;
  margin-top: calc(-1 * var(--bs-gutter-y));
  margin-right: calc(-0.5 * var(--bs-gutter-x));
  margin-left: calc(-0.5 * var(--bs-gutter-x));
}
.ppo .row > * {
  flex-shrink: 0; width: 100%; max-width: 100%;
  margin-top: var(--bs-gutter-y);
  padding-right: calc(var(--bs-gutter-x) * 0.5);
  padding-left: calc(var(--bs-gutter-x) * 0.5);
}
.ppo .d-flex { display: flex !important; }
.ppo .flex-wrap { flex-wrap: wrap !important; }
.ppo .flex-column { flex-direction: column !important; }
.ppo .align-items-start { align-items: flex-start !important; }
.ppo .align-items-center { align-items: center !important; }
.ppo .justify-content-between { justify-content: space-between !important; }
.ppo .justify-content-center { justify-content: center !important; }
.ppo .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.ppo .col-12 { flex: 0 0 auto; width: 100%; }
.ppo .col-6 { flex: 0 0 auto; width: 50%; }
@media (min-width: 768px) {
  .ppo .col-md-6 { flex: 0 0 auto; width: 50%; }
}
@media (min-width: 992px) {
  .ppo .col-lg-3 { flex: 0 0 auto; width: 25%; }
  .ppo .col-lg-4 { flex: 0 0 auto; width: 33.33333333%; }
  .ppo .col-lg-6 { flex: 0 0 auto; width: 50%; }
  .ppo .col-lg-8 { flex: 0 0 auto; width: 66.66666667%; }
  .ppo .col-lg-9 { flex: 0 0 auto; width: 75%; }
}

/* Progressive enhancement only. Nothing load-bearing lives below this line:
   the store deletes it and the page must not care. */
.ppo .ppbtn:hover { opacity: 0.92; }
.ppo details.ppfaq > summary { cursor: pointer; }
.ppo details.ppfaq > summary::-webkit-details-marker { display: none; }
.ppo details.ppfaq > summary::marker { content: ""; }
.ppo details.ppfaq:hover { border-color: #fa7268; }
.ppo details.ppfaq[open] .ppfaq-chev { transform: rotate(180deg); }
.ppo .ppfaq-chev { transition: transform 0.18s ease; }
.ppo a { overflow-wrap: anywhere; }
@media (max-width: 820px) {
  .ppo h1 { font-size: 32px !important; }
  .ppo h2 { font-size: 23px !important; }
}
@media (prefers-reduced-motion: reduce) {
  .ppo .ppfaq-chev { transition: none; }
}
"""

DOCUMENT = """<!doctype html>
<html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>
            %s
        </title>
        <meta name="description" content="%s" />
        <!-- NO EXTERNAL RESOURCE IS LOADED FROM THIS FILE, on purpose.
     The vendor guidelines allow only resources inside static/description,
     canonical YouTube links, Microsoft Teams links, mailto: and skype:, and
     they forbid JavaScript. The store strips <head> anyway, so a Bootstrap CDN
     link or a font stylesheet here would buy nothing on the store page and
     would leave third-party hosts in a file a reviewer reads. The store page
     serves Bootstrap 5 itself, and the STYLE block inside div.ppo restates the
     handful of grid/flex rules this page uses, so the layout also holds when
     the file is opened straight off disk - only in the system font. -->
    </head>
    <body>
        %s
%s
    </body>
</html>
"""

# Named entities, so the copy survives a paste into the store form. The
# reference listing is pure ASCII for exactly this reason.
NAMED = {
    "—": "mdash", "–": "ndash", "’": "rsquo", "‘": "lsquo",
    "“": "ldquo", "”": "rdquo", "·": "middot", "×": "times",
    "…": "hellip", "→": "rarr", "←": "larr", "€": "euro",
    " ": "nbsp", "©": "copy", "®": "reg", "™": "trade",
    "°": "deg", "•": "bull", "½": "frac12", "≤": "le",
    "≥": "ge", "≈": "asymp", "é": "eacute", "è": "egrave",
    "£": "pound", "‹": "lsaquo", "›": "rsaquo",
}


def to_ascii(text):
    out = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
        elif ch in NAMED:
            out.append("&%s;" % NAMED[ch])
        else:
            out.append("&#%d;" % ord(ch))
    return "".join(out)


# --------------------------------------------------------------------------
def read_css(raw):
    css = "".join(re.findall(r"(?is)<style[^>]*>(.*?)</style>", raw))
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # strip @media blocks: responsiveness is handled by Bootstrap breakpoints
    out, i = [], 0
    while True:
        m = re.search(r"@media[^{]*\{", css[i:])
        if not m:
            out.append(css[i:])
            break
        out.append(css[i:i + m.start()])
        j = i + m.end()
        depth = 1
        while depth and j < len(css):
            depth += (css[j] == "{") - (css[j] == "}")
            j += 1
        i = j
    return "".join(out)


def expand_vars(css):
    variables = {}
    for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;}]+)", css):
        variables.setdefault(m.group(1), " ".join(m.group(2).split()))
    for _ in range(5):
        for k, v in list(variables.items()):
            variables[k] = re.sub(r"var\(\s*(--[a-z0-9-]+)\s*(?:,[^)]*)?\)",
                                  lambda mm: variables.get(mm.group(1), ""), v)

    def sub(text):
        for _ in range(5):
            new = re.sub(r"var\(\s*(--[a-z0-9-]+)\s*(?:,\s*([^)]*))?\)",
                         lambda mm: variables.get(mm.group(1), mm.group(2) or ""), text)
            if new == text:
                break
            text = new
        return text

    return sub(css), variables


def parse_rules(css):
    """[(order, specificity, selector, [(prop, value, important)])]"""
    rules = []
    order = 0
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sels, block = m.group(1), m.group(2)
        decls = []
        for d in block.split(";"):
            if ":" not in d:
                continue
            p, _, v = d.partition(":")
            p = p.strip().lower()
            v = " ".join(v.split())
            if not p or p.startswith("--"):
                continue
            imp = "!important" in v
            v = v.replace("!important", "").strip()
            decls.append((p, v, imp))
        if not decls:
            continue
        for sel in sels.split(","):
            sel = " ".join(sel.split())
            if not sel:
                continue
            order += 1
            rules.append((order, sel, decls))
    return rules


# Pseudo-classes that are structural and safe to resolve at build time.
SAFE_PSEUDO = re.compile(r":(not\(|first-child|last-child|only-child|nth-child\(|nth-of-type\(|first-of-type|last-of-type)")


def skip_selector(sel):
    """True for anything that must not be flattened into a style attribute.

    Legacy single-colon pseudo-elements matter here: `.ppprice-bul li:before`
    was being matched against the <li> itself, which stamped the marker dot's
    `width:7px;height:7px` onto every list item and collapsed the text to one
    character per line.
    """
    if "[open]" in sel or "-webkit-" in sel:
        return True
    stripped = SAFE_PSEUDO.sub("", sel)
    return ":" in stripped


def build_cascade(tree, rules):
    """element -> OrderedDict(prop -> (value, important, specificity, order))"""
    computed = {}
    trans = cssselect.HTMLTranslator()
    for order, sel, decls in rules:
        if skip_selector(sel):
            continue
        try:
            parsed = cssselect.parse(sel)
            xp = trans.selector_to_xpath(parsed[0])
            spec = parsed[0].specificity()
        except Exception:
            continue
        try:
            targets = tree.xpath(xp)
        except Exception:
            continue
        for el in targets:
            slot = computed.setdefault(el, OrderedDict())
            for p, v, imp in decls:
                prev = slot.get(p)
                key = (imp, spec, order)
                if prev is None or key >= (prev[1], prev[2], prev[3]):
                    slot[p] = (v, imp, spec, order)
    return computed


def classes(el):
    return (el.get("class") or "").split()


def add_class(el, names):
    if not names:
        return
    have = classes(el)
    for n in names.split():
        if n not in have:
            have.append(n)
    el.set("class", " ".join(have))


def px(value):
    m = re.match(r"^([\d.]+)px$", value.strip())
    return float(m.group(1)) if m else None


# --------------------------------------------------------------------------
# Custom class names that are NOT pp-prefixed collide with classes the store
# page already defines. Bootstrap's own .mark (yellow highlight) was winning
# over the listing's .mark, putting a cream box behind the hero's coral words.
RENAME_CLASSES = ["mark", "narrow", "plaincol", "sec-alt", "sec-tight",
                  "sec-warm", "sec", "wrap"]


def prefix_custom_classes(raw):
    """Rename unprefixed custom classes in the markup AND the stylesheet."""
    n = 0
    for name in RENAME_CLASSES:
        # class attributes
        def fix_attr(m):
            nonlocal n
            parts = m.group(2).split()
            parts = [("pp-" + p) if p == name else p for p in parts]
            n += 1
            return '%s="%s"' % (m.group(1), " ".join(parts))

        raw = re.sub(r'(class)="([^"]*\b%s\b[^"]*)"' % re.escape(name), fix_attr, raw)
        # selectors
        raw = re.sub(r"\.%s\b(?![-\w])" % re.escape(name), ".pp-" + name, raw)
    return raw


def main():
    raw = open(SRC, encoding="utf-8").read()
    import os
    if os.path.exists("header.txt"):
        header_comment = open("header.txt", encoding="utf-8").read().rstrip()
    else:
        m = re.search(r"(?s)<body>\s*(<!--.*?-->)", raw)
        header_comment = m.group(1) if m else ""
    raw = prefix_custom_classes(raw)

    css = read_css(raw)
    css, variables = expand_vars(css)
    rules = parse_rules(css)

    doc = LH.fromstring(raw)
    root = doc.body.cssselect(".ppo")[0]

    computed = build_cascade(doc, rules)

    GAPS = {}
    NOSHRINK_LATER = []
    stats = {"inlined": 0, "shadow2border": 0, "bg2bgcolor": 0, "dropped": {}}

    # ---------- 1. write the cascade into inline styles ----------
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        decls = OrderedDict()
        for p, (v, imp, _s, _o) in computed.get(el, {}).items():
            decls[p] = (v, imp)
        # the element's own style attribute wins over the stylesheet
        for d in (el.get("style") or "").split(";"):
            if ":" in d:
                p, _, v = d.partition(":")
                v = " ".join(v.split())
                imp = "!important" in v
                decls[p.strip().lower()] = (v.replace("!important", "").strip(), imp)
        if not decls:
            continue

        cls_to_add = []
        final = OrderedDict()
        own = set(classes(el))

        for p, (v, imp) in decls.items():
            # background shorthand -> background-color (no gradients on this page)
            if p == "background":
                if "gradient" in v or "url(" in v:
                    stats["dropped"][p] = stats["dropped"].get(p, 0) + 1
                    continue
                p = "background-color"
                stats["bg2bgcolor"] += 1

            if p == "box-shadow":
                key = re.sub(r"\s*,\s*", ",", v.replace(" 0 0 0", " 0 0 0")).replace(", ", ",")
                key = re.sub(r"\s+", " ", key).replace("( ", "(").replace(" )", ")")
                key = key.replace(", ", ",")
                width, color = SHADOW_BORDER.get(key, ("__unknown__", None))
                if width == "__unknown__":
                    # ring-only shadows ("0 0 0 Npx <color>") become borders,
                    # everything else becomes a hairline
                    ring = re.match(r"^0 0 0 ([\d.]+px) (.+)$", v)
                    width, color = (ring.group(1), ring.group(2)) if ring else ("1px", "#eae0f2")
                if width and "border-width" not in decls and "border" not in decls:
                    final["border-width"] = (width, False)
                    final["border-style"] = ("solid", False)
                    final["border-color"] = (color, False)
                    stats["shadow2border"] += 1
                continue

            if p in ("gap", "row-gap", "column-gap"):
                # keep the stylesheet's exact value; phase 7 turns it into
                # inline margins. Snapping to Bootstrap's gap scale turned the
                # pill nav's 2px gap into 16px and the 7px icon gaps into 4px.
                parts = [x for x in (px(t) for t in v.split()) if x is not None]
                if parts:
                    GAPS[el] = max(parts)
                continue
            if p == "flex-direction" and v == "column":
                cls_to_add.append("flex-column")
                continue
            if p == "flex-wrap" and v == "wrap":
                cls_to_add.append("flex-wrap")
                continue
            if p == "align-items":
                cls_to_add.append({"center": "align-items-center",
                                   "flex-start": "align-items-start",
                                   "start": "align-items-start",
                                   "flex-end": "align-items-end",
                                   "stretch": "align-items-stretch",
                                   "baseline": "align-items-baseline"}.get(v, ""))
                continue
            if p == "justify-content":
                cls_to_add.append({"center": "justify-content-center",
                                   "space-between": "justify-content-between",
                                   "space-around": "justify-content-around",
                                   "flex-start": "justify-content-start",
                                   "flex-end": "justify-content-end"}.get(v, ""))
                continue
            if p == "flex" and v in ("none", "0 0 auto"):
                # flex-shrink-0 is out of the house vocabulary; a fixed-size
                # item is pinned with min-width, which does survive
                NOSHRINK_LATER.append(el)
                continue
            if p in ("flex", "flex-grow") and v in ("1", "1 1 0", "1 1 0%", "1 1 auto"):
                # `flex:1` on the rail connector became a flex-fill class that
                # the vocabulary pass then stripped, leaving the line 0px wide
                # and invisible. width:100% shrinks to the free space in a flex
                # row, which is what flex:1 did, and it survives the sanitiser.
                if "width" not in final:
                    final["width"] = ("100%", imp)
                continue
            if p in ("list-style", "list-style-type") and v.startswith("none"):
                if el.tag in ("ul", "ol"):
                    cls_to_add.append("list-unstyled")
                continue
            if p in ("overflow-x", "overflow") and v in ("auto", "scroll"):
                cls_to_add.append("table-responsive")
                continue

            # Odoo's _style_whitelist carries border-top and border-bottom but
            # NOT border-left / border-right, so those shorthands must be split.
            if p in ("border-left", "border-right"):
                side = p.split("-")[1]
                m = re.match(r"^([\d.]+(?:px)?)\s+(\w+)\s+(.+)$", v)
                if m:
                    final["border-%s-width" % side] = (m.group(1), imp)
                    final["border-%s-style" % side] = (m.group(2), imp)
                    final["border-%s-color" % side] = (m.group(3), imp)
                    continue
                if v.strip() in ("0", "0px", "none"):
                    final["border-%s-width" % side] = ("0", imp)
                    continue

            if p in DROP_PROPS or p not in STYLE_ALLOWLIST:
                stats["dropped"][p] = stats["dropped"].get(p, 0) + 1
                continue

            final[p] = (v, imp)

        # a grid container's display is replaced by Bootstrap .row
        if final.get("display", ("", False))[0] == "grid":
            gname = next((c for c in own if c in GRID), None)
            if gname and GRID[gname][0] and "row" in (GRID[gname][0] or ""):
                final.pop("display", None)

        add_class(el, " ".join(c for c in cls_to_add if c))
        if final:
            el.set("style", ";".join(
                "%s:%s%s" % (p, v, " !important" if imp else "")
                for p, (v, imp) in final.items()))
            stats["inlined"] += 1
        elif el.get("style"):
            del el.attrib["style"]

    # a flex item that must not shrink: pin its measured width with min-width
    for el in NOSHRINK_LATER:
        m = re.search(r"\bwidth:\s*([\d.]+px)", el.get("style") or "")
        if m:
            cur = OrderedDict()
            for d in (el.get("style") or "").split(";"):
                if ":" in d:
                    k, _, v2 = d.partition(":")
                    cur[k.strip()] = v2.strip()
            cur.setdefault("min-width", m.group(1))
            el.set("style", ";".join("%s:%s" % kv for kv in cur.items()))

    # ---------- 2. grid containers -> Bootstrap rows ----------
    def set_style_props(el, decls):
        """Set properties on an element's style attribute, overriding any the
        cascade already wrote (a prepend would lose: last declaration wins)."""
        cur = OrderedDict()
        for d in (el.get("style") or "").split(";"):
            if ":" in d:
                p, _, v = d.partition(":")
                cur[p.strip()] = v.strip()
        for d in decls.split(";"):
            if ":" in d:
                p, _, v = d.partition(":")
                cur[p.strip()] = v.strip()
        el.set("style", ";".join("%s:%s" % kv for kv in cur.items()))

    prepend_style = set_style_props

    def has_h_padding(el):
        st = el.get("style") or ""
        return bool(re.search(r"\bpadding(-left|-right)?\s*:", st))

    def as_column(kid, col_cls, gutter):
        """Give `kid` a Bootstrap column, wrapping it when the gutter needs
        padding that must not land inside the card's own border."""
        gx, gy = gutter or (0, 0)
        if any(c.startswith("col-") for c in classes(kid)):
            col = kid                        # the listing already wrapped it
            add_class(col, col_cls or "")
        elif gx or gy:
            col = etree.Element("div")
            parent = kid.getparent()
            parent.insert(parent.index(kid), col)
            col.append(kid)
            add_class(col, col_cls or "col-12")
            # CSS grid stretched its items for free; a Bootstrap column
            # stretches but the card inside it does not, so cards in one row
            # ended at different heights and any margin-top:auto stopped
            # bottom-aligning. height:100% restores both.
            set_style_props(kid, "height:100%")
        else:
            col = kid
            add_class(col, col_cls or "")
        # a column is sized by its class: inline width:auto / display:block win
        st = re.sub(r"\bwidth:\s*auto;?", "", col.get("style") or "")
        st = re.sub(r"\bdisplay:\s*(block|grid);?", "", st)
        col.set("style", st.strip(";"))
        if col is kid and not (gx or gy) and has_h_padding(col):
            # a flush row whose halves carry their own padding: writing
            # padding-left:0 here wiped the panel's 26px inner padding
            return col
        pad = "padding-left:%dpx;padding-right:%dpx" % (gx // 2, gx // 2)
        if gy:
            pad += ";padding-bottom:%dpx" % gy
        prepend_style(col, pad)
        return col

    for name, (cont_cls, child_cls, gutter) in GRID.items():
        for el in root.cssselect("." + name):
            add_class(el, cont_cls)
            if cont_cls:
                keep = set(cont_cls.split())
                el.set("class", " ".join(
                    c for c in classes(el)
                    if c in keep or not re.fullmatch(r"(gap|g|gx|gy)-\d", c)))
                if "row" in keep or "d-flex" in keep:
                    st = re.sub(r"\bdisplay:\s*(grid|flex);?", "",
                                el.get("style") or "")
                    el.set("style", st.strip(";"))
            if gutter:
                # this container's spacing is now the row gutter below, so the
                # stylesheet `gap` must NOT also become margins in phase 7 --
                # that stacked both and pushed columns onto extra lines
                GAPS.pop(el, None)
                gx, gy = gutter
                neg = "margin-left:-%dpx;margin-right:-%dpx" % (gx // 2, gx // 2)
                if gy:
                    neg += ";margin-bottom:-%dpx" % gy
                prepend_style(el, neg)
            kids = [k for k in el if isinstance(k.tag, str)]
            pos = POS_CHILD.get(name)
            for i, kid in enumerate(kids):
                cls = child_cls
                if pos and i < len(pos):
                    cls = pos[i]
                elif pos:
                    continue
                if cls or gutter:
                    as_column(kid, cls, gutter)
    for name, col in CHILD_COL.items():
        for el in root.cssselect("." + name):
            add_class(el, col)
            st = re.sub(r"\bwidth:\s*auto;?", "", el.get("style") or "")
            el.set("style", st.strip(";"))
            if not has_h_padding(el):
                prepend_style(el, "padding-left:0;padding-right:0")

    # ---------- 3. flex containers -> display:flex + Bootstrap utilities ----------
    for name, extra in FLEX.items():
        for el in root.cssselect("." + name):
            add_class(el, extra)
            st = el.get("style") or ""
            if "display:" not in st:
                disp = "inline-flex" if name in ("ppbtn", "ppframe-dots", "ppslot-tag") else "flex"
                el.set("style", ("display:%s;" % disp) + st)
    for name in NOSHRINK:
        for el in root.cssselect("." + name):
            add_class(el, "flex-shrink-0")
    # the jump menu must be the part of the nav that gives way, not the CTA
    for el in root.cssselect(".pptabs"):
        add_class(el, "flex-fill flex-wrap justify-content-center")
    for el in root.cssselect(".ppnav-brand, .ppnav-cta"):
        add_class(el, "flex-shrink-0")

    # ---------- 4. CSS-only decoration -> real markup ----------
    def prepend_marker(el, glyph, style):
        """Turn `el` into a flex row: [marker][everything it already held].

        A floated marker is not an option: floats escape their <li>/<div> and
        stack against each other, which collapsed the price list to one
        character per line.
        """
        body_div = etree.Element("div")
        body_div.set("style", "min-width:0")
        body_div.text = el.text
        el.text = None
        for child in list(el):
            body_div.append(child)
        marker = etree.Element("span")
        marker.set("style", style)
        marker.text = glyph
        add_class(marker, "flex-shrink-0")
        el.append(marker)
        el.append(body_div)
        st = el.get("style") or ""
        st = re.sub(r"padding-left:\s*[\d.]+px;?", "", st)
        if "display:" not in st:
            st = "display:flex;" + st
        el.set("style", st)
        add_class(el, "align-items-start gap-2")

    # coral diamond marker on the capability rows (.ppcap-i::before)
    for el in root.cssselect(".ppcap-i"):
        prepend_marker(el, "◆", "color:#fa7268;font-size:11px;font-weight:700;line-height:1.9")

    # coral dot bullets inside the violet price card (.ppprice-bul li:before)
    for ul in root.cssselect(".ppprice-bul"):
        add_class(ul, "list-unstyled")
        for li in ul.findall("li"):
            prepend_marker(li, "•", "color:#fa7268;font-size:15px;font-weight:700;line-height:1.35")

    # FAQ: the chevron stays. Its rotation and the hidden native marker live in
    # the fallback STYLE block as progressive enhancement, the way the Advanced
    # Sales Analysis listing does it.
    for summ in root.cssselect(".ppfaq summary"):
        set_style_props(summ, "display:flex")
        add_class(summ, "d-flex align-items-center justify-content-between")

    # the comparison table keeps its sideways scroll through Bootstrap
    for wrap in root.cssselect(".pptblwrap"):
        add_class(wrap, "table-responsive")

    # `white-space:nowrap` survives but the `overflow:hidden;text-overflow:ellipsis`
    # that used to clip these monospace frame labels does not, so on a phone the
    # label pushed the whole page sideways. Let them wrap instead.
    for el in root.cssselect(".ppframe-l"):
        el.set("style", re.sub(r"white-space:\s*nowrap;?", "",
                               el.get("style") or "").strip(";"))

    # ---------- 5. every <img> gets real width/height ----------
    ICON = {}
    for m in re.finditer(r"\.ppico-(\d+)\s*\{([^}]*)\}", css):
        w = re.search(r"width:\s*([\d.]+)px", m.group(2))
        if w:
            ICON["ppico-" + m.group(1)] = int(float(w.group(1)))
    imgs_fixed = 0
    for img in root.iter("img"):
        cls = classes(img)
        size = next((ICON[c] for c in cls if c in ICON), None)
        st = img.get("style") or ""
        if size:
            img.set("width", str(size))
            img.set("height", str(size))
            if "width:" not in st:
                img.set("style", ("width:%dpx;height:%dpx;" % (size, size)) + st)
            imgs_fixed += 1
        elif not (img.get("width") and img.get("height")):
            # full-width product shots: let the box decide, but pin a max
            if "width:" not in st:
                img.set("style", "display:block;width:100%;height:auto;max-width:100%;" + st)
            imgs_fixed += 1

    # ---------- 6. anchors must beat the store's own link styling ----------
    for a in root.iter("a"):
        st = a.get("style") or ""
        if "color:" in st and "!important" not in st:
            st = re.sub(r"color:\s*([^;]+)", lambda m: "color:%s !important" % m.group(1).strip(), st, count=1)
        if "text-decoration" not in st:
            st = st.rstrip(";") + ";text-decoration:none !important"
        a.set("style", st.lstrip(";"))

    # ---------- 6b. rounded containers must clip their own children ----------
    # `overflow` is not a surviving property, so a container that used
    # `overflow:hidden` to clip a child inside its rounded corners no longer
    # does: the hero GIF's square corners poked straight through the frame's
    # 20px radius. Hand the corner radii to the children instead, which
    # border-*-radius can do from inside the whitelist.
    CLIP_CONTAINERS = {"ppframe": "vertical", "ppfaq": "vertical",
                       "ppba": "horizontal", "ppprice": "horizontal"}
    clipped = 0

    def style_px(el, prop):
        m = re.search(r"\b%s:\s*([\d.]+)px" % re.escape(prop),
                      el.get("style") or "")
        return float(m.group(1)) if m else None

    for name, orientation in CLIP_CONTAINERS.items():
        for cont in root.cssselect("." + name):
            radius = style_px(cont, "border-radius")
            if not radius:
                continue
            inner = max(0.0, radius - (style_px(cont, "border-width") or 0))
            if not inner:
                continue
            r = ("%g" % inner) + "px"
            kids = [k for k in cont if isinstance(k.tag, str) and k.tag != "style"]
            if not kids:
                continue
            corners = {}
            if len(kids) == 1:
                corners[0] = ["top-left", "top-right", "bottom-right", "bottom-left"]
            elif orientation == "vertical":
                corners[0] = ["top-left", "top-right"]
                corners[len(kids) - 1] = ["bottom-left", "bottom-right"]
            else:
                corners[0] = ["top-left", "bottom-left"]
                corners[len(kids) - 1] = ["top-right", "bottom-right"]
            for idx, which in corners.items():
                kid = kids[idx]
                decls = ";".join("border-%s-radius:%s" % (c, r) for c in which)
                set_style_props(kid, decls)
                clipped += 1
                # a flush image paints over its own box, so it needs the radii
                # too; an image sitting on a padded bed never reaches the corner
                if not has_h_padding(kid):
                    imgs = kid.findall("img") or kid.findall(".//img")
                    if len(imgs) == 1:
                        set_style_props(imgs[0], decls)

    # ---------- 7. house class vocabulary ----------
    # The Advanced Sales Analysis listing sticks to a small set of Bootstrap
    # classes and does every other bit of spacing with inline margins, which
    # survive the sanitiser AND still work with no stylesheet at all. Follow it:
    # gap-*, flex-fill, flex-shrink-0 and flex-lg-nowrap all go away.
    gaps_converted = 0
    for el, g in GAPS.items():
        cs = classes(el)
        column = "flex-column" in cs
        wraps = "flex-wrap" in cs
        kids = [k for k in el if isinstance(k.tag, str)]
        if g and kids:
            step = "%g" % g

            def followed_by_more(k):
                """A flex item needs the gap margin when something comes after
                it -- another element, or a bare text node. Icons followed only
                by text (`<img>Sales orders only`) were losing their 7px gap
                because text nodes are not element children."""
                if k is not kids[-1]:
                    return True
                return bool((k.tail or "").strip())

            if column:
                for k in kids:
                    if followed_by_more(k):
                        set_style_props(k, "margin-bottom:%spx" % step)
            else:
                for k in kids:
                    if followed_by_more(k):
                        set_style_props(k, "margin-right:%spx" % step)
                if wraps:
                    for k in kids:
                        set_style_props(k, "margin-bottom:%spx" % step)
                    set_style_props(el, "margin-bottom:-%spx" % step)
        gaps_converted += 1
    for el in root.cssselect(".flex-fill, .flex-shrink-0, .flex-lg-nowrap"):
        el.set("class", " ".join(c for c in classes(el)
                                 if c not in ("flex-fill", "flex-shrink-0",
                                              "flex-lg-nowrap")))
    # `list-unstyled` is not in the house vocabulary and `list-style` is not a
    # surviving property, so a <ul> whose markers were replaced by real spans
    # becomes a <div>: no marker can come back.
    for ul in root.cssselect("ul.list-unstyled, ul.pprel-list, ul.ppprice-bul"):
        ul.tag = "div"
        ul.set("class", " ".join(c for c in classes(ul) if c != "list-unstyled"))
        set_style_props(ul, "padding-left:0;margin-left:0")
        for li in ul.findall("li"):
            li.tag = "div"

    # ---------- 8. store-legal link form and complete alt text ----------
    for a in root.iter("a"):
        h = a.get("href") or ""
        # root-relative keeps the link on the store's own host, which is how the
        # reference listing writes its cross-sell buttons
        if h.startswith("https://apps.odoo.com/"):
            a.set("href", h[len("https://apps.odoo.com"):])
        for attr in ("target", "rel"):
            if a.get(attr):
                del a.attrib[attr]
    for img in root.iter("img"):
        if img.get("alt") is None:
            img.set("alt", "")

    # ---------- 9. emit the full document, the way the reference does ----------
    for st in list(root.iter("style")):
        st.getparent().remove(st)
    fallback = etree.fromstring("<style>%s</style>" % FALLBACK_CSS)
    root.insert(0, fallback)

    frag = LH.tostring(root, encoding="unicode", method="html", pretty_print=False)
    # lxml closes wbr; it is a void element and a closing tag is a parse error
    for void in ("wbr", "br", "hr", "img", "col"):
        frag = frag.replace("</%s>" % void, "")
    out = DOCUMENT % (TITLE, DESCRIPTION, header_comment, frag)
    out = to_ascii(out)
    open(OUT, "w", encoding="utf-8").write(out)
    print("gap utilities converted to inline margins: %d" % gaps_converted)
    print("rounded containers given child corner radii:  %d" % clipped)

    print("inlined declarations on %d elements" % stats["inlined"])
    print("box-shadow -> border conversions: %d" % stats["shadow2border"])
    print("background -> background-color:  %d" % stats["bg2bgcolor"])
    print("images given explicit size:      %d" % imgs_fixed)
    print("declarations dropped (not renderable inline):")
    for p, n in sorted(stats["dropped"].items(), key=lambda kv: -kv[1])[:20]:
        print("   %-24s %d" % (p, n))


if __name__ == "__main__":
    main()
