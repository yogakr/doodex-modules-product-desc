#!/usr/bin/env python3
"""
make_versions.py - derive the 16.0 / 18.0 / 19.0 listings from the Odoo 17 one.

    python3 tools/make_versions.py            # all three
    python3 tools/make_versions.py 19

Pipeline, in order:
  1. read ../static/description/index.html  (the published Odoo 17 listing)
  2. run tools/debootstrap.py over it, so the layout is real table markup and
     depends on no stylesheet - the store does not reliably serve Bootstrap to
     the description fragment
  3. apply the substitutions below
  4. write advanced_sales_analysis_<v>/static/description/index.html

The layout, the copy and every inline style stay exactly as the 17 listing has
them. Only the substitutions in SUBS change, and each one is anchored on a
literal string that is asserted to exist, so a reworded 17 listing fails loudly
instead of silently producing a wrong page.

VERSION-NEUTRAL PROOF. The screenshots and GIFs were captured on an Odoo 17
database and the automated test count was measured there. Restating either as
if it had been re-measured on 16, 18 or 19 would be a claim we cannot support,
so those two strings lose their version instead. Everything else that names a
version is genuinely per-edition and is rewritten.

/apps/modules/17.0/... is deliberately NOT rewritten: that is where the other
Doodex listings actually are, whatever version this page is built for.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from debootstrap import convert  # noqa: E402

VERSIONS = ['16', '18', '19']

# Rewrites applied to the de-bootstrapped 17 page. Each entry is
# (literal to find, replacement template, expected occurrences).
# {V} -> "19.0", {S} -> "19"
SUBS = [
    # --- the two claims that must lose their version, not gain a new one -----
    ('37 automated tests, run against a vanilla Odoo 17.0 database',
     '37 automated tests, shipped inside the module', 1),
    ('live Odoo 17 database', 'live Odoo database', 1),

    # --- the FAQ answer about supported versions ----------------------------
    ('This is the Odoo 17.0 edition, and this page describes that build. If '
     'you run 16 or 18, write to us and we will tell you honestly where those '
     'builds stand rather than sell you the wrong one.',
     'This is the Odoo {V} edition, and this page describes that build. '
     'Advanced Sales Analysis is published separately for the other supported '
     'Odoo versions &mdash; if you run a version you cannot find on the store, '
     'write to us and we will tell you honestly where that build stands '
     'rather than sell you the wrong one.', 1),

    # --- plain version numbers ---------------------------------------------
    ('17.0.1.0.0', '{V}.1.0.0', 2),
    ('Odoo 17.0', 'Odoo {V}', None),   # whatever is left after the above
    ('Odoo 17', 'Odoo {S}', None),
]

LINK_TOKEN = '\x00APPSLINK\x00'

# lxml parses &mdash; into the character itself and serialises it back as raw
# UTF-8. The store serves the description fragment with no charset of its own,
# so a raw UTF-8 byte is read as Windows-1252 and shown as mojibake - the exact
# bug reported after an earlier upload. Everything non-ASCII goes back to an
# entity before the file is written.
ENTITIES = {
    '\xa0': '&nbsp;', '\u2014': '&mdash;', '\u2013': '&ndash;',
    '\u00b7': '&middot;', '\u2018': '&lsquo;', '\u2019': '&rsquo;',
    '\u201c': '&ldquo;', '\u201d': '&rdquo;', '\u2192': '&rarr;',
    '\u2190': '&larr;', '\u2026': '&hellip;', '\u00d7': '&times;',
    '\u00a9': '&copy;', '\u00ae': '&reg;', '\u2122': '&trade;',
}


def to_ascii(html: str) -> str:
    """Re-encode every non-ASCII character as an HTML entity."""
    out = []
    for ch in html:
        if ord(ch) < 128:
            out.append(ch)
        else:
            out.append(ENTITIES.get(ch, '&#%d;' % ord(ch)))
    return ''.join(out)



def build(src_17: str, key: str) -> str:
    html, stats = convert(src_17)
    if stats['leftover_bootstrap']:
        raise SystemExit('debootstrap left Bootstrap classes behind: %s'
                         % stats['leftover_bootstrap'])

    # protect the cross-sell links before any version rewriting
    html = html.replace('/apps/modules/17.0/', LINK_TOKEN)

    v, s = key + '.0', key
    for find, repl, expect in SUBS:
        # the 17 listing is pretty-printed, so a phrase can carry newlines and
        # indentation inside it: match on whitespace-insensitive text
        pattern = re.compile(r'\s+'.join(re.escape(w) for w in find.split()))
        n = len(pattern.findall(html))
        if expect is not None and n != expect:
            raise SystemExit('expected %d occurrence(s) of %r in the 17 '
                             'listing, found %d. The source was reworded - '
                             'update SUBS.' % (expect, find[:60], n))
        html = pattern.sub(
            lambda _m, r=repl: r.replace('{V}', v).replace('{S}', s), html)

    html = html.replace(LINK_TOKEN, '/apps/modules/17.0/')

    # The Specifications table holds the Odoo version as a bare value with no
    # "Odoo" in front of it, so none of the substitutions above reach it. Anchor
    # on its label cell. Caught by comparing the rendered 17 and 19 pages side
    # by side - a plain search for "17" cannot find it among the font sizes,
    # the #171717 colours and ic-chevron-17.png.
    spec = re.compile(r'(>\s*Odoo version\s*</td>.*?<td[^>]*>\s*)17\.0(\s*</td>)',
                      re.S)
    if len(spec.findall(html)) != 1:
        raise SystemExit('expected exactly one Specifications "Odoo version" '
                         'cell holding 17.0, found %d'
                         % len(spec.findall(html)))
    html = spec.sub(lambda m: m.group(1) + v + m.group(2), html, count=1)

    # The 17 listing's own header comment describes a Bootstrap layout. After
    # debootstrap that is no longer true, and a file must not misdescribe
    # itself, so the two passages that name Bootstrap are rewritten.
    comment_subs = [
        ('and all grid/flex layout is done with Bootstrap classes',
         'and all grid/flex layout is real TABLE markup - not one Bootstrap '
         'class is left on this page, because the store does not reliably '
         'serve Bootstrap to the description fragment and without it every '
         'multi-column block collapses into one column'),
        ('justify-content           -> Bootstrap row/col + d-flex utility classes',
         'justify-content           -> a real TABLE: table-layout:fixed for '
         'equal columns, border-spacing for the gutter, and the card IS the TD '
         'so cells in a row are the same height by definition'),
    ]
    for find, repl in comment_subs:
        pattern = re.compile(r'\s+'.join(re.escape(w) for w in find.split()))
        if not pattern.search(html):
            raise SystemExit('the 17 header comment was reworded, cannot fix '
                             'its Bootstrap description: %r' % find[:50])
        html = pattern.sub(lambda _m, r=repl: r, html, count=1)

    # The STYLE block is rewritten wholesale. What the 17 listing had there was
    # written for a Bootstrap page: a grid fallback for .row/.col-* (now dead,
    # those classes are gone) and a box-sizing rule (load-bearing, which is the
    # one thing this block must never be - the store kills it, and every element
    # carrying both a width and a padding would then change size). What replaces
    # it is progressive enhancement only, plus the mobile unstack for the new
    # tables so a phone matches what Bootstrap used to do with col-md-*.
    new_style = """<style>
/* ==========================================================================
   NOT LOAD-BEARING. Every rule that matters is an inline style using a
   property on Odoo's whitelist, and the whole layout is real table markup.
   Delete this element and the page is unchanged in substance - that is the
   test, and tools/check_store_html.py performs it.

   NO box-sizing rule on purpose. The store kills this block, so a box-sizing
   declared here would silently resize every element that carries both a size
   and a padding the moment the page is published.

   What lives here:
     * hover and [open] states, which cannot be inlined at all;
     * the FAQ chevron flip;
     * the mobile collapse, which turns the layout tables into a single column
       under 820px - the job col-md-* used to do. With this block killed the
       tables stay side by side on a phone and get narrow.
   ========================================================================== */
.asa img { max-width: 100%; }

/* hover / open states */
.asa .asa-jump:hover { background-color: #ffffff; color: #270140; }
.asa details.asa-faq > summary { cursor: pointer; list-style: none; }
.asa details.asa-faq > summary::-webkit-details-marker { display: none; }
.asa details.asa-faq > summary::marker { content: ""; }
.asa details.asa-faq:hover { border-color: #fa7268; }
.asa details.asa-faq[open] { background-color: #faf7fc; border-color: #fa7268; }
.asa details.asa-faq[open] .asa-chev-img { transform: rotate(180deg); }
.asa .asa-chev-img { transition: transform 0.18s ease; }
.asa a { overflow-wrap: anywhere; }

@media (max-width: 820px) {
   .asa h1 { font-size: 32px !important; }
   .asa h2 { font-size: 23px !important; }

   /* the layout tables become one column, which is what col-md-* did */
   .asa table.lay,
   .asa table.lay tbody,
   .asa table.lay tr,
   .asa table.lay td { display: block !important; width: auto !important; }
   .asa table.lay td { margin-bottom: 14px; }
   .asa table.lay td:empty { display: none !important; }

   /* the chapter numeral sits above its heading instead of beside it */
   .asa .asa-chap,
   .asa .asa-chap-c {
      display: block !important;
      width: auto !important;
      padding-right: 0 !important;
   }
   .asa .asa-chap-c span[style*="56px"] { font-size: 40px !important; }

   /* HOW IT WORKS: the left edge between steps becomes a top edge */
   .asa .asa-how-c {
      border-left-width: 0 !important;
      border-top-width: 1px !important;
      border-top-style: solid !important;
      border-top-color: #ece4f3 !important;
   }
   .asa .asa-how-c:first-child { border-top-width: 0 !important; }
}

@media (prefers-reduced-motion: reduce) {
   .asa .asa-chev-img { transition: none; }
}
</style>"""
    m_style = re.search(r'<style[^>]*>.*?</style>', html, re.S)
    if not m_style:
        raise SystemExit('no STYLE block found in the converted page')
    html = html[:m_style.start()] + new_style + html[m_style.end():]

    # the generated file says so, and says how to regenerate it
    banner = (
        '<!-- ======================================================================\n'
        '  GENERATED FILE - do not edit by hand.\n'
        '  Built from ../static/description/index.html (the Odoo 17.0 listing) by\n'
        '      python3 tools/make_versions.py %s\n'
        '  which runs tools/debootstrap.py over it (Bootstrap layout -> table\n'
        '  markup, because the store does not reliably serve Bootstrap to the\n'
        '  description fragment) and then applies the version substitutions.\n'
        '  Edit the 17.0 listing, or tools/make_versions.py, and run it again.\n'
        '  Verify with: python3 tools/check_store_html.py <this file>\n'
        '  ====================================================================== -->\n'
        % key)
    m = re.search(r'<body[^>]*>', html)
    if m:
        html = html[:m.end()] + '\n' + banner + html[m.end():]

    return to_ascii(html)


def main(argv):
    keys = [a for a in argv[1:] if not a.startswith('-')] or VERSIONS
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    src_path = os.path.normpath(
        os.path.join(root, os.pardir, 'static', 'description', 'index.html'))
    if not os.path.exists(src_path):
        print('the Odoo 17 listing was not found at %s' % src_path,
              file=sys.stderr)
        return 2
    src_17 = open(src_path, encoding='utf-8').read()
    print('source: %s (%d bytes)' % (src_path, len(src_17)))

    for key in keys:
        if key not in VERSIONS:
            print('unknown version %r (have %s)' % (key, ', '.join(VERSIONS)),
                  file=sys.stderr)
            return 2
        html = build(src_17, key)
        non_ascii = sorted({c for c in html if ord(c) > 127})
        if non_ascii:
            print('non-ASCII characters in the %s output: %r'
                  % (key, non_ascii), file=sys.stderr)
            return 2
        dest = os.path.join(root, 'advanced_sales_analysis_%s' % key,
                            'static', 'description', 'index.html')
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'w', encoding='ascii', newline='\n') as fh:
            fh.write(html)
        print('wrote %s (%d bytes)' % (dest, len(html)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
