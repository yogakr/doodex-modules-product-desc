#!/usr/bin/env python3
"""
prune_unused_assets.py - move every file under static/description/assets that
index.html does not reference into _sources/description/, so the module ships
only what the listing actually displays.

    python tools/prune_unused_assets.py --dry-run    # show the plan, change nothing
    python tools/prune_unused_assets.py              # move them to _sources/
    python tools/prune_unused_assets.py --delete     # delete them instead (no undo)

The unused list is DERIVED, not hardcoded: the script reads index.html, collects
every "./assets/..." reference, walks the assets tree and treats the difference
as unused. So it stays correct after you edit the listing - re-run it any time.

Nothing is deleted by default. Files keep their relative path and land in
_sources/description/assets/... at the module root. _sources/ sits outside
static/, so it never ships with the module, and the raw screenshots stay
available for regenerating the GIFs.

Left alone on purpose:
  * static/description/icon.png   - read by __manifest__.py, not by index.html
  * static/description/banner.gif - not under assets/
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

REF_RE = re.compile(r'(?:src|href)\s*=\s*"\./(assets/[^"]+)"')


def find_paths(start: str):
    """tools/<this script> -> module root -> the paths the script works with."""
    module_root = os.path.dirname(os.path.dirname(os.path.abspath(start)))
    description = os.path.join(module_root, 'static', 'description')
    return (module_root,
            description,
            os.path.join(description, 'assets'),
            os.path.join(description, 'index.html'),
            os.path.join(module_root, '_sources', 'description'))


def referenced_assets(index_html: str) -> set[str]:
    with open(index_html, encoding='utf-8') as fh:
        html = fh.read()
    return {m.group(1) for m in REF_RE.finditer(html)}


def files_on_disk(assets_root: str) -> list[tuple[str, str, int]]:
    out = []
    for dirpath, _dirnames, filenames in os.walk(assets_root):
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = 'assets/' + os.path.relpath(full, assets_root).replace(os.sep, '/')
            out.append((rel, full, os.path.getsize(full)))
    return sorted(out)


def prune_empty_dirs(assets_root: str, log) -> None:
    for dirpath, _dirnames, _filenames in sorted(
            os.walk(assets_root, topdown=False), key=lambda t: -len(t[0])):
        if dirpath == assets_root:
            continue
        if not os.listdir(dirpath):
            os.rmdir(dirpath)
            log('  removed empty folder: %s'
                % os.path.relpath(dirpath, assets_root))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true',
                    help='print the plan and exit without touching anything')
    ap.add_argument('--delete', action='store_true',
                    help='delete the unused files instead of archiving them')
    ap.add_argument('--root', default=__file__,
                    help=argparse.SUPPRESS)  # used by the test harness
    args = ap.parse_args(argv)

    module_root, description, assets_root, index_html, sources_root = \
        find_paths(args.root)
    for p in (description, assets_root, index_html):
        if not os.path.exists(p):
            print('not found: %s' % p, file=sys.stderr)
            return 2

    referenced = referenced_assets(index_html)
    if not referenced:
        print('index.html contains no ./assets reference - refusing to run. '
              'That is almost certainly a parsing problem rather than a tree '
              'full of dead files.', file=sys.stderr)
        return 2

    on_disk = files_on_disk(assets_root)
    unused = [(rel, full, size) for rel, full, size in on_disk
              if rel not in referenced]

    verb = 'DELETE' if args.delete else 'MOVE'
    print()
    print('module        : %s' % module_root)
    print('referenced    : %d files' % len(referenced))
    print('on disk       : %d files' % len(on_disk))
    print('unused        : %d files, %d KB'
          % (len(unused), sum(s for _, _, s in unused) / 1024))
    if not args.delete:
        print('destination   : %s' % sources_root)
    print()

    missing = sorted(r for r in referenced
                     if not os.path.exists(os.path.join(description, r)))
    for m in missing:
        print('  WARNING  index.html references a file that does not exist: %s' % m)
    if missing:
        print()

    if not unused:
        print('nothing to do - every asset on disk is used by index.html.')
        return 0

    for rel, _full, size in unused:
        print('  %-6s %9s  %s' % (verb, '{:,}'.format(size), rel))
    print()

    if args.dry_run:
        print('dry run - nothing was changed. '
              'Re-run without --dry-run to apply.')
        return 0

    done = skipped = 0
    for rel, full, size in unused:
        if args.delete:
            os.remove(full)
            done += 1
            continue
        dest = os.path.join(sources_root, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            # archived by an earlier run; just drop the copy under static/
            if os.path.getsize(dest) == size:
                os.remove(full)
                print('  already in _sources, removed the static copy: %s' % rel)
                done += 1
            else:
                print('  WARNING  destination exists with a different size, '
                      'left alone: %s' % rel)
                skipped += 1
            continue
        shutil.move(full, dest)
        done += 1

    prune_empty_dirs(assets_root, print)

    print()
    print('%d file(s) %s, %d skipped.'
          % (done, 'deleted' if args.delete else 'moved', skipped))
    print('Now confirm the listing still resolves every image:')
    print('  python tools/check_store_html.py static/description/index.html')
    return 0


if __name__ == '__main__':
    sys.exit(main())
