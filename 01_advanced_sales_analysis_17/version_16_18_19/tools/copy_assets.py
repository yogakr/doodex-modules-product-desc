#!/usr/bin/env python3
"""
copy_assets.py - give each generated listing its own copy of the images it
actually references.

    python3 tools/copy_assets.py --dry-run
    python3 tools/copy_assets.py

Each module ships independently, so every version folder needs its own
static/description/assets tree. The list is DERIVED from the generated
index.html of each folder, so only the images that listing really uses are
copied - not the whole asset library.

Source is the published Odoo 17 module that these listings were derived from:
    ../static/description/assets          (01_advanced_sales_analysis_17)
Override it with --source if the tree lives somewhere else.

Existing files are left alone unless --force is given, so re-running is safe.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

REF_RE = re.compile(r'src\s*=\s*"\./(assets/[^"]+)"')


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)                    # version_16_18_19/
    default_src = os.path.normpath(
        os.path.join(root, os.pardir, 'static', 'description', 'assets'))

    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default=default_src,
                    help='assets tree to copy from (default: %s)' % default_src)
    ap.add_argument('--dry-run', action='store_true',
                    help='print what would be copied and exit')
    ap.add_argument('--force', action='store_true',
                    help='overwrite files that already exist at the destination')
    args = ap.parse_args(argv)

    if not os.path.isdir(args.source):
        print('source assets tree not found: %s\n'
              'Pass --source with the path to the Odoo 17 module\'s '
              'static/description/assets folder.' % args.source,
              file=sys.stderr)
        return 2

    targets = sorted(
        d for d in os.listdir(root)
        if d.startswith('advanced_sales_analysis_')
        and os.path.isfile(os.path.join(root, d, 'static', 'description',
                                        'index.html')))
    if not targets:
        print('no generated listing found. Run tools/build_listing.py first.',
              file=sys.stderr)
        return 2

    print('source: %s' % args.source)
    total_copied = total_skipped = 0
    missing_any = False

    for folder in targets:
        desc = os.path.join(root, folder, 'static', 'description')
        with open(os.path.join(desc, 'index.html'), encoding='utf-8') as fh:
            refs = sorted({m.group(1) for m in REF_RE.finditer(fh.read())})
        print('\n%s  -  %d referenced image(s)' % (folder, len(refs)))

        copied = skipped = 0
        for rel in refs:
            src = os.path.join(args.source, rel[len('assets/'):]
                               .replace('/', os.sep))
            dest = os.path.join(desc, rel.replace('/', os.sep))
            if not os.path.exists(src):
                print('   MISSING in source: %s' % rel)
                missing_any = True
                continue
            if os.path.exists(dest) and not args.force:
                skipped += 1
                continue
            if args.dry_run:
                print('   COPY %s' % rel)
                copied += 1
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
        print('   %d copied, %d already present' % (copied, skipped))
        total_copied += copied
        total_skipped += skipped

    print('\n%d file(s) %s, %d already present.'
          % (total_copied, 'would be copied' if args.dry_run else 'copied',
             total_skipped))
    if missing_any:
        print('Some images are missing from the source tree - the listings '
              'that reference them will not render until you supply them.')
        return 1
    if not args.dry_run:
        print('Now check each listing:')
        for folder in targets:
            print('  python3 tools/check_store_html.py '
                  '%s/static/description/index.html' % folder)
    return 0


if __name__ == '__main__':
    sys.exit(main())
