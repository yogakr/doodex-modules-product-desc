#!/usr/bin/env python3
"""
check_store_html.py - does static/description/index.html survive the Odoo Apps
Store, and does it pass the vendor guidelines?

Run it after every edit to the listing:

    pip install lxml lxml_html_clean
    python3 tools/check_store_html.py static/description/index.html

What it does
------------
1. Reproduces odoo.tools.mail.html_sanitize() from Odoo 17 (tag kill-list,
   allowed-tag list, safe_attrs, the inline-CSS property whitelist) and runs it
   over the file, twice:
     * DEFAULT  - html_sanitize() with Odoo's default flags. <style> is killed,
                  inline style attributes and classes are kept as-is.
     * STRICT   - sanitize_attributes=True, sanitize_style=True. Every inline
                  CSS property outside the whitelist is deleted too. This is the
                  worst case; design for it and the page cannot break.
   It then reports every tag that was dropped and every element that lost
   attributes.
2. Lints the source against the apps.odoo.com vendor guidelines and the store
   sandbox: script tags, external hosts, non-whitelisted CSS properties, tags
   outside the allowed list, missing asset files, unbalanced markup, non-ASCII
   bytes, and duplicate id attributes.

Exit code is 1 if any ERROR was reported, 0 otherwise. WARNINGs do not fail.

Written for the Advanced Sales Analysis listing; it is generic and works on any
Odoo store description.
"""
from __future__ import annotations

import collections
import os
import re
import sys

try:
    from lxml import etree
    from lxml import html as lhtml
    from lxml.html import defs
except ImportError:
    sys.exit("lxml is required:  pip install lxml lxml_html_clean")

try:
    from lxml_html_clean import Cleaner as _BaseCleaner
except ImportError:  # lxml < 5.2 shipped the cleaner itself
    from lxml.html.clean import Cleaner as _BaseCleaner


# --------------------------------------------------------------------------
# Odoo 17 - odoo/tools/mail.py
# --------------------------------------------------------------------------
SAFE_ATTRS = defs.safe_attrs | frozenset([
    'style',
    'data-o-mail-quote', 'data-o-mail-quote-node',
    'data-oe-model', 'data-oe-id', 'data-oe-field', 'data-oe-type',
    'data-oe-expression', 'data-oe-translation-initial-sha', 'data-oe-nodeid',
    'data-last-history-steps', 'data-oe-protected', 'data-oe-transient-content',
    'data-width', 'data-height', 'data-scale-x', 'data-scale-y', 'data-x', 'data-y',
    'data-publish', 'data-id', 'data-res_id', 'data-interval', 'data-member_id',
    'data-scroll-background-ratio', 'data-view-id',
    'data-class', 'data-mimetype', 'data-original-src', 'data-original-id',
    'data-gl-filter', 'data-quality', 'data-resize-width',
    'data-shape', 'data-shape-colors', 'data-file-name', 'data-original-mimetype',
    'data-behavior-props', 'data-prop-name',
    'data-mimetype-before-conversion',
    'data-bs-toggle',
])

ALLOWED_TAGS = defs.tags | frozenset(
    'article bdi section header footer hgroup nav aside figure main'.split()
    + [etree.Comment])

SANITIZE_TAGS = {
    'allow_tags': ALLOWED_TAGS,
    'kill_tags': ['base', 'embed', 'frame', 'head', 'iframe', 'link', 'meta',
                  'noscript', 'object', 'script', 'style', 'title'],
    'remove_tags': ['html', 'body'],
}

STYLE_WHITELIST = frozenset([
    'font-size', 'font-family', 'font-weight', 'font-style', 'background-color',
    'color', 'text-align', 'line-height', 'letter-spacing', 'text-transform',
    'text-decoration', 'opacity', 'float', 'vertical-align', 'display',
    'padding', 'padding-top', 'padding-left', 'padding-bottom', 'padding-right',
    'margin', 'margin-top', 'margin-left', 'margin-bottom', 'margin-right',
    'white-space',
    'border', 'border-color', 'border-radius', 'border-style', 'border-width',
    'border-top', 'border-bottom',
    'height', 'width', 'max-width', 'min-width', 'min-height',
    'border-collapse', 'border-spacing', 'caption-side', 'empty-cells',
    'table-layout',
] + ['border-%s-%s' % (p, a)
     for p in ('top', 'bottom', 'left', 'right')
     for a in ('style', 'color', 'width', 'left-radius', 'right-radius')])

_STYLE_RE = re.compile(r'''([\w-]+)\s*:\s*((?:[^;"']|"[^";]*"|'[^';]*')+)''')

# Vendor guidelines: only these leave the page.
ALLOWED_LINK_PREFIXES = ('mailto:', 'skype:', '#', './', 'assets/', '/apps/')
ALLOWED_EXTERNAL_HOSTS = ('youtube.com', 'youtu.be', 'teams.microsoft.com',
                          'teams.live.com')


class _Cleaner(_BaseCleaner):
    _style_whitelist = STYLE_WHITELIST
    strip_classes = False
    sanitize_style = False

    def __call__(self, doc):
        super().__call__(doc)
        if not getattr(self, 'safe_attrs_only', False) and self.strip_classes:
            for el in doc.iter(tag=etree.Element):
                el.attrib.pop('class', None)
        if not self.style and self.sanitize_style:
            for el in doc.iter(tag=etree.Element):
                self._parse_style(el)

    def _parse_style(self, el):
        styling = el.attrib.get('style')
        if not styling:
            return
        valid = collections.OrderedDict()
        for prop, val in _STYLE_RE.findall(styling):
            if prop.lower() in self._style_whitelist:
                valid[prop.lower()] = val
        if valid:
            el.attrib['style'] = '; '.join('%s:%s' % kv for kv in valid.items())
        else:
            del el.attrib['style']


def html_sanitize(src, sanitize_tags=True, sanitize_attributes=False,
                  sanitize_style=False, sanitize_form=True,
                  strip_style=False, strip_classes=False):
    """odoo.tools.mail.html_sanitize, minus the html_normalize wrapper."""
    kwargs = {
        'page_structure': True,
        'style': strip_style,
        'sanitize_style': sanitize_style,
        'forms': sanitize_form,
        'remove_unknown_tags': False,
        'comments': False,
        'processing_instructions': False,
    }
    if sanitize_tags:
        kwargs.update(SANITIZE_TAGS)
    if sanitize_attributes:
        attrs = SAFE_ATTRS - frozenset(['class']) if strip_classes else SAFE_ATTRS
        kwargs.update({'safe_attrs_only': True, 'safe_attrs': attrs})
    else:
        kwargs.update({'safe_attrs_only': False, 'strip_classes': strip_classes})
    doc = lhtml.fromstring(src)
    _Cleaner(**kwargs)(doc)
    return lhtml.tostring(doc, encoding='unicode')


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
ERRORS: list[str] = []
WARNINGS: list[str] = []


def error(msg):
    ERRORS.append(msg)
    print('  ERROR    ' + msg)


def warn(msg):
    WARNINGS.append(msg)
    print('  WARNING  ' + msg)


def ok(msg):
    print('  ok       ' + msg)


def section(title):
    print('\n' + title)
    print('-' * len(title))


def tag_counts(src):
    doc = lhtml.fromstring(src)
    return collections.Counter(e.tag for e in doc.iter() if isinstance(e.tag, str))


# --------------------------------------------------------------------------
def check_sandbox(src):
    section('1. Store sandbox (what html_sanitize would remove)')

    if re.search(r'<script', src, re.I):
        error('a <script> tag is present. The sanitiser kills it and the vendor '
              'guidelines forbid JavaScript. Remove it.')
    else:
        ok('no <script> tag')

    used = set(tag_counts(src))
    unknown = sorted(t for t in used if t not in ALLOWED_TAGS
                     and t not in SANITIZE_TAGS['kill_tags']
                     and t not in SANITIZE_TAGS['remove_tags'])
    if unknown:
        error('tags outside the allowed list, they are unwrapped and lose their '
              'styling: ' + ', '.join(unknown))
    else:
        ok('every tag is in the allowed list (or is head/style, killed on purpose)')

    for label, kwargs in (('default flags', {}),
                          ('strict flags', dict(sanitize_attributes=True,
                                                sanitize_style=True))):
        out = html_sanitize(src, **kwargs)
        before, after = tag_counts(src), tag_counts(out)
        killed = {t: (before[t], after.get(t, 0)) for t in before
                  if before[t] != after.get(t, 0)}
        expected = set(SANITIZE_TAGS['kill_tags']) | {'html', 'body', 'div'}
        surprise = {t: v for t, v in killed.items() if t not in expected}
        if surprise:
            error('%s: unexpected tag losses %s' % (label, surprise))
        else:
            ok('%s: only head/style/script/html/body are removed %s'
               % (label, sorted(killed)))

    # inline CSS properties
    props = collections.Counter()
    for m in re.finditer(r'style\s*=\s*"([^"]*)"', src):
        for decl in m.group(1).split(';'):
            if ':' in decl:
                props[decl.split(':', 1)[0].strip().lower()] += 1
    bad = {p: n for p, n in props.items() if p and p not in STYLE_WHITELIST}
    if bad:
        warn('inline CSS properties outside Odoo\'s whitelist, dropped under '
             'strict flags: ' + ', '.join('%s (x%d)' % (p, n)
                                          for p, n in sorted(bad.items())))
    else:
        ok('every inline CSS property is on Odoo\'s whitelist (%d declarations)'
           % sum(props.values()))

    if re.search(r'<style', src, re.I):
        warn('a <style> block is present. Some store pages keep it and some kill '
             'it, so nothing load-bearing may live there - keep it to hover '
             'states, media queries and other progressive enhancement.')


def check_guidelines(src, path):
    section('2. Vendor guidelines (apps.odoo.com/apps/vendor-guidelines)')

    urls = re.findall(r'(?:href|src)\s*=\s*"([^"]+)"', src)
    externals = [u for u in urls if not u.startswith(ALLOWED_LINK_PREFIXES)]
    flagged = [u for u in externals
               if not any(h in u for h in ALLOWED_EXTERNAL_HOSTS)]
    if flagged:
        error('links or resources outside static/description. Only mailto:, '
              'skype:, canonical YouTube, Microsoft Teams and same-folder '
              'resources are allowed: ' + ', '.join(sorted(set(flagged))))
    else:
        ok('no forbidden href/src (%d links, all mailto:/anchor/local/apps.odoo.com)'
           % len(urls))

    # naked external addresses in the copy, and QR images, are the same thing to
    # a reviewer as a link. Look at the rendered text, not the source, because a
    # single address is often split across a <b> or <span> boundary.
    text = lhtml.fromstring(src).text_content()
    naked = sorted(set(re.findall(
        r'(?:[a-z0-9-]+\.)+(?:com|net|org|io|co|id|me)(?:/[\w./-]*)?', text)))
    naked = [n for n in naked
             if not any(h in n for h in ALLOWED_EXTERNAL_HOSTS)
             and not n.startswith(('cdn.', 'fonts.'))]
    phones = sorted(set(re.findall(r'\+\d[\d\s().-]{7,}\d', text)))
    if phones:
        warn('phone numbers in the copy: ' + ', '.join(phones)
             + ' - the guidelines list mailto: and skype: as the contact '
               'channels, a phone or WhatsApp number is neither')
    if naked:
        warn('external addresses written as plain text in the copy - a reviewer '
             'reads these as external links even though they are not clickable: '
             + ', '.join(naked))
    if re.search(r'qr-', src):
        warn('QR code images are present. A QR that encodes an address outside '
             'static/description is an external link in image form.')

    base = os.path.dirname(os.path.abspath(path))
    missing = [u for u in urls if u.startswith('./')
               and not os.path.exists(os.path.join(base, u[2:]))]
    if missing:
        error('referenced asset files do not exist: ' + ', '.join(missing))
    else:
        ok('every ./assets reference resolves to a file on disk')

    with open(path, 'rb') as fh:
        raw = fh.read()
    try:
        raw.decode('ascii')
        ok('file is pure ASCII, so no encoding can mangle it on paste')
    except UnicodeDecodeError:
        warn('file contains non-ASCII bytes. Prefer HTML entities (&mdash;, '
             '&ldquo;) so the copy survives a paste into the store form.')


def check_markup(src):
    section('3. Markup health')

    parser = etree.HTMLParser(recover=True)
    lhtml.fromstring(src, parser=parser)
    if parser.error_log:
        for e in list(parser.error_log)[:12]:
            warn('parser: line %s: %s' % (e.line, e.message))
    else:
        ok('parses with no recoverable errors')

    ids = re.findall(r'\sid="([^"]+)"', src)
    dupes = [i for i, n in collections.Counter(ids).items() if n > 1]
    if dupes:
        error('duplicate id attributes: ' + ', '.join(dupes))
    else:
        ok('%d unique ids' % len(ids))
    unprefixed = [i for i in ids if not re.match(r'^[a-z]{2,5}-', i)]
    if unprefixed:
        warn('ids without a module prefix can collide with the store page\'s own '
             'ids: ' + ', '.join(unprefixed))

    anchors = set(re.findall(r'href="#([^"]+)"', src))
    for a in sorted(anchors - set(ids)):
        error('jump link #%s has no matching id' % a)

    imgs = re.findall(r'<img\b[^>]*>', src, re.I)
    no_alt = [i for i in imgs if 'alt=' not in i]
    if no_alt:
        warn('%d <img> without an alt attribute' % len(no_alt))
    else:
        ok('all %d images carry an alt attribute' % len(imgs))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'static/description/index.html'
    src = open(path, encoding='utf-8').read()
    print('checking %s (%d bytes)' % (path, len(src)))
    check_sandbox(src)
    check_guidelines(src, path)
    check_markup(src)
    section('Result')
    print('  %d error(s), %d warning(s)' % (len(ERRORS), len(WARNINGS)))
    if ERRORS:
        print('  the listing is NOT safe to upload yet')
    else:
        print('  no blocking problem found')
    return 1 if ERRORS else 0


if __name__ == '__main__':
    sys.exit(main())
