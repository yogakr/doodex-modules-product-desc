#!/usr/bin/env python3
"""
debootstrap.py - rewrite the Bootstrap layout of the Odoo 17 Advanced Sales
Analysis listing into real table markup, keeping every inline style untouched.

    python3 tools/debootstrap.py <source index.html> <output index.html>

Why: the store does not reliably serve Bootstrap to the description fragment.
Without it every `.row` collapses into a single column and the gutters vanish -
the "layout melar / kolom runtuh" symptom. Tables need no stylesheet at all.

What it rewrites, and nothing else:

  .asa-chap row g-0 align-items-start   ->  display:table + two display:table-cell
      divs. This is the markup the page had before it was briefly converted to
      Bootstrap columns; it is restored verbatim.

  .row g-N with uniform col-* children  ->  <table table-layout:fixed>, the
      children become <td>. border-spacing carries the gutter and the wrapper's
      negative margin cancels the outer spacing so cell edges still line up with
      the surrounding text. Bootstrap's g-0/g-3/g-4 map to 0 / 16 / 24 px.

  div.d-flex with two children          ->  a two-cell table, first cell
      shrink-to-fit. These are all icon + text rows.

  span.d-flex ... justify-content-between (FAQ summary) -> two-cell table with
      the second cell right-aligned.

  the header's three-way flex row       ->  a three-cell table (left / centre /
      right), the same shape 07_personal_email_usage_17 uses.

  the hero button row                   ->  text-align:center on the container;
      the buttons are already inline-block.

  the changelog version row             ->  a plain div; its children are
      inline-block spans that flow on one line by themselves.

  .table-responsive                     ->  the class is kept so the STYLE
      block can still add overflow-x when it survives, but nothing depends on
      it: both tables fit the 1032px column.

Every Bootstrap class is removed from the output. Verify with
tools/check_store_html.py, and by rendering the output with NO stylesheet
against the original WITH Bootstrap - they must match.
"""
from __future__ import annotations

import re
import sys

from lxml import html as lh
from lxml import etree

GUTTER = {'g-0': 0, 'g-1': 4, 'g-2': 8, 'g-3': 16, 'g-4': 24, 'g-5': 48}
COL_RE = re.compile(r'^col(-(sm|md|lg|xl|xxl))?(-(\d+|auto))?$')
BS_CLASSES = {
    'row', 'd-flex', 'flex-wrap', 'align-items-start', 'align-items-center',
    'align-items-end', 'justify-content-between', 'justify-content-center',
    'justify-content-start', 'justify-content-end',
} | set(GUTTER)

LINE = '#ece4f3'


def classes(el) -> list[str]:
    return (el.get('class') or '').split()


def strip_bs(el) -> None:
    keep = [c for c in classes(el)
            if c not in BS_CLASSES and not COL_RE.match(c)]
    if keep:
        el.set('class', ' '.join(keep))
    elif el.get('class') is not None:
        del el.attrib['class']


def add_style(el, extra: str) -> None:
    cur = (el.get('style') or '').strip().rstrip(';')
    el.set('style', (cur + '; ' + extra).lstrip('; ') if cur else extra)


def frag(html: str):
    return lh.fragment_fromstring(html)


def cols_per_row(cells) -> int:
    """Read the column width off the first child's col-* class."""
    for c in cells:
        for cl in classes(c):
            m = COL_RE.match(cl)
            if m and m.group(4) and m.group(4) != 'auto':
                n = int(m.group(4))
                if 1 <= n <= 12:
                    return max(1, 12 // n)
    return len(cells)


def gutter_of(el) -> int:
    for cl in classes(el):
        if cl in GUTTER:
            return GUTTER[cl]
    return 24  # Bootstrap's default --bs-gutter-x is 1.5rem


def build_table(cells, per_row: int, gx: int, gy: int, valign: str,
                fixed: bool = True):
    """Return a wrapper div holding a table whose <td>s are `cells`."""
    margin = ('margin: %dpx %dpx' % (-gy, -gx)) if (gx or gy) else 'margin: 0'
    wrapper = frag('<div style="%s"></div>' % margin)
    style = ('width: 100%%; %sborder-collapse: separate; '
             'border-spacing: %dpx %dpx'
             % ('table-layout: fixed; ' if fixed else '', gx, gy))
    table = frag('<table class="lay" style="%s"><tbody></tbody></table>' % style)
    tbody = table.find('tbody')
    for i in range(0, len(cells), per_row):
        chunk = cells[i:i + per_row]
        tr = etree.SubElement(tbody, 'tr')
        for cell in chunk:
            td = etree.SubElement(tr, 'td')
            strip_bs(cell)
            # move the cell's own presentation onto the td, keep its children
            if cell.get('style'):
                td.set('style', cell.get('style'))
            if cell.get('class'):
                td.set('class', cell.get('class'))
            add_style(td, 'vertical-align: %s' % valign)
            if cell.text:
                td.text = cell.text
            for kid in list(cell):
                td.append(kid)
        # keep the fixed columns even on a short last row
        for _ in range(per_row - len(chunk)):
            pad = etree.SubElement(tr, 'td')
            pad.set('style', 'vertical-align: %s' % valign)
    wrapper.append(table)
    return wrapper


def convert(src: str) -> tuple[str, dict]:
    doc = lh.fromstring(src)
    stats = {'chap': 0, 'row': 0, 'flex2': 0, 'faq': 0, 'header': 0,
             'herobtn': 0, 'changelog': 0}

    # ---- 1. chapter heading: back to the display:table markup it had before
    for el in list(doc.iter()):
        if not isinstance(el.tag, str):
            continue
        if 'asa-chap' in classes(el) and 'row' in classes(el):
            kids = [k for k in el if isinstance(k.tag, str)]
            if len(kids) != 2:
                continue
            strip_bs(el)
            el.set('style', 'display: table; width: 100%')
            num, body = kids
            strip_bs(num)
            num.set('style', 'display: table-cell; vertical-align: top; '
                             'width: 96px; padding-right: 16px')
            strip_bs(body)
            body.set('style', 'display: table-cell; vertical-align: top')
            stats['chap'] += 1

    # ---- 2. header three-way row
    for el in list(doc.iter()):
        if not isinstance(el.tag, str):
            continue
        cl = set(classes(el))
        if {'d-flex', 'justify-content-between'} <= cl and 'flex-wrap' in cl:
            kids = [k for k in el if isinstance(k.tag, str)]
            if len(kids) != 3:
                continue
            strip_bs(el)
            tbl = frag(
                '<table class="lay" style="width: 100%; '
                'border-collapse: collapse; border-spacing: 0px 0px">'
                '<tbody><tr></tr></tbody></table>')
            tr = tbl.find('tbody/tr')
            aligns = [
                'vertical-align: middle; width: 1px; white-space: nowrap; '
                'padding-right: 18px',
                'vertical-align: middle; text-align: center',
                'vertical-align: middle; text-align: right; width: 1px; '
                'white-space: nowrap; padding-left: 18px']
            for kid, al in zip(kids, aligns):
                td = etree.SubElement(tr, 'td')
                td.set('style', al)
                td.append(kid)
            el.append(tbl)
            stats['header'] += 1

    # ---- 3. hero button row and the changelog version row
    for el in list(doc.iter()):
        if not isinstance(el.tag, str):
            continue
        cl = set(classes(el))
        if 'd-flex' in cl and 'justify-content-center' in cl:
            strip_bs(el)
            add_style(el, 'text-align: center')
            stats['herobtn'] += 1
        elif ('d-flex' in cl and 'flex-wrap' in cl
              and 'align-items-center' in cl and 'justify-content-between' not in cl):
            strip_bs(el)
            stats['changelog'] += 1

    # ---- 4. .row grids
    for el in list(doc.iter()):
        if not isinstance(el.tag, str):
            continue
        if 'row' not in classes(el):
            continue
        kids = [k for k in el if isinstance(k.tag, str)]
        if not kids:
            continue
        per = cols_per_row(kids)
        g = gutter_of(el)
        gy = g
        valign = 'middle' if 'align-items-center' in classes(el) else 'top'
        wrapper = build_table(kids, per, g, gy, valign)
        strip_bs(el)
        for k in kids:
            el.remove(k)
        el.append(wrapper)
        stats['row'] += 1

    # ---- 5. FAQ summary rows, then the plain two-child icon+text flexes
    for el in list(doc.iter()):
        if not isinstance(el.tag, str):
            continue
        cl = set(classes(el))
        if not ('d-flex' in cl):
            continue
        kids = [k for k in el if isinstance(k.tag, str)]
        if len(kids) != 2:
            continue
        between = 'justify-content-between' in cl
        strip_bs(el)
        tbl = frag('<table style="width: 100%; border-collapse: collapse; '
                   'border-spacing: 0px 0px"><tbody><tr></tr></tbody></table>')
        tr = tbl.find('tbody/tr')
        if between:
            styles = ['vertical-align: top',
                      'vertical-align: top; text-align: right; width: 1px; '
                      'white-space: nowrap']
            stats['faq'] += 1
        else:
            styles = ['vertical-align: top; width: 1px', 'vertical-align: top']
            stats['flex2'] += 1
        for kid, st in zip(kids, styles):
            td = etree.SubElement(tr, 'td')
            td.set('style', st)
            td.append(kid)
        if el.text and el.text.strip():
            tbl.getchildren()  # keep lxml happy; text is preserved below
        el.append(tbl)

    # a <span> can no longer hold a table once it is a layout box
    for el in doc.iter():
        if isinstance(el.tag, str) and el.tag == 'span' and el.find('table') is not None:
            el.tag = 'div'

    out = lh.tostring(doc, encoding='unicode')
    leftover = sorted({c for m in re.finditer(r'class="([^"]*)"', out)
                       for c in m.group(1).split()
                       if c in BS_CLASSES or COL_RE.match(c)})
    stats['leftover_bootstrap'] = leftover
    return out, stats


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src = open(argv[1], encoding='utf-8').read()
    out, stats = convert(src)
    with open(argv[2], 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(out)
    for k, v in stats.items():
        print('  %-20s %s' % (k, v))
    print('wrote %s (%d bytes)' % (argv[2], len(out)))
    return 1 if stats['leftover_bootstrap'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
