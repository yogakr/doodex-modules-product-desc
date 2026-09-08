#!/usr/bin/env python3
"""Reproduce what the Odoo Apps Store sanitizer does to a listing description.

Model verified empirically (2026-09-03) against two live Doodex listings:
  apps.odoo.com/apps/modules/17.0/marketing_crm_automation_dashboard_campaign_doodex
  apps.odoo.com/apps/modules/17.0/flow_survey

Observed facts:
  * <style> blocks inside the description: 0 on both pages  -> killed
  * <head>/<meta>/<link>/<title>: absent                    -> killed
  * inline style="" attributes: kept (1522 / 1132 elements) BUT the union of
    CSS properties present across both pages is exactly 46 and contains no
    box-shadow / position / flex / gap / grid-* / transform / overflow /
    background-shorthand -> property allowlist enforced
  * HTML5 tags survive: section 21, nav 1, details 22, summary 22, wbr 6, hr 10
  * attributes survive: aria-label, loading, crossorigin, open, name, target, rel
  * Bootstrap 5 utility classes are live on the store page
  * apps.odoo.com / youtube.com / mailto: hrefs survive
"""
import re
import sys

# Odoo's _style_whitelist, transcribed to match tools/check_store_html.py from
# the Advanced Sales Analysis listing (the house reference). Note what is NOT
# here: border-left and border-right have no shorthand entry, only their
# longhands, and there is no max-height. The 46 properties observed live on the
# two published listings are all inside this set.
STYLE_ALLOWLIST = set(
    """font-size font-family font-weight font-style background-color
    color text-align line-height letter-spacing text-transform
    text-decoration opacity float vertical-align display
    padding padding-top padding-left padding-bottom padding-right
    margin margin-top margin-left margin-bottom margin-right
    white-space
    border border-color border-radius border-style border-width
    border-top border-bottom
    height width max-width min-width min-height
    border-collapse border-spacing caption-side empty-cells
    table-layout""".split()
) | {
    "border-%s-%s" % (side, attr)
    for side in ("top", "bottom", "left", "right")
    for attr in ("style", "color", "width", "left-radius", "right-radius")
}

KILL_TAGS = ["style", "script", "link", "meta", "title", "head", "base",
             "iframe", "embed", "object", "noscript"]


def filter_style(value):
    kept, dropped = [], []
    for decl in value.split(";"):
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop_n = prop.strip().lower()
        if prop_n in STYLE_ALLOWLIST:
            kept.append(f"{prop_n}:{val.strip()}")
        else:
            dropped.append(prop_n)
    return ";".join(kept), dropped


def sanitize(html):
    stats = {"styles_killed": 0, "props_dropped": {}}

    # kill <head> and everything in it
    html = re.sub(r"(?is)<!doctype[^>]*>", "", html)
    html = re.sub(r"(?is)<head\b.*?</head\s*>", "", html)
    html = re.sub(r"(?is)</?html[^>]*>", "", html)
    html = re.sub(r"(?is)</?body[^>]*>", "", html)

    # kill tags (element + content)
    for tag in KILL_TAGS:
        html, n = re.subn(r"(?is)<%s\b.*?</%s\s*>" % (tag, tag), "", html)
        if tag == "style":
            stats["styles_killed"] = n
        html = re.sub(r"(?is)<%s\b[^>]*/?>" % tag, "", html)

    html = re.sub(r"(?s)<!--.*?-->", "", html)

    # property-filter every inline style attribute
    def repl(m):
        kept, dropped = filter_style(m.group(1))
        for d in dropped:
            stats["props_dropped"][d] = stats["props_dropped"].get(d, 0) + 1
        return ' style="%s"' % kept if kept else ""

    html = re.sub(r'\sstyle="([^"]*)"', repl, html)
    return html, stats


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    out, st = sanitize(open(src, encoding="utf-8").read())
    open(dst, "w", encoding="utf-8").write(out)
    print("style blocks killed:", st["styles_killed"])
    if st["props_dropped"]:
        print("inline properties dropped by the store:")
        for p, n in sorted(st["props_dropped"].items(), key=lambda kv: -kv[1]):
            print("   %-24s %d" % (p, n))
    else:
        print("inline properties dropped by the store: none")
