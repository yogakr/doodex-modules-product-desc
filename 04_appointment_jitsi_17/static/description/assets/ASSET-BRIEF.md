# Asset brief — Appointment Jitsi store listing

## The media, in full

| | Format | Count | State |
|---|---|---|---|
| Hero | GIF, 968×310, 4 beats | 1 | **Done** — real footage |
| Features band | none — copy and icons | 0 | By design |
| Use Cases band | none — copy and icons | 0 | By design |
| Icons + QR codes | PNG | 42 | Final, do not replace |

**There is one image on this page and it is the hero.** Every other band carries
its argument in copy, with icons for rhythm. Nothing here is waiting on a capture
session — the media job is finished.

## Read this if you ever add an image back

**Author it at exactly 2× the width it renders at.** This decides whether a
capture is readable on the page, and the hero went through three attempts before
it landed.

| Slot | Renders at | So author at |
|---|---|---|
| Hero (split hero, right column) | ~484 px | **968** px wide |
| Anything in a two-column band | ~496 px | **1000** px wide |

Inside that canvas, **crop to the one control that matters and upscale it 2×**, so
the Odoo UI lands at its own native size on screen. At a 496 px slot you can show
roughly 496 px of *native* Odoo width legibly and no more — the Jitsi
Configuration block is 432 px native, so it fits; a whole Odoo window does not, at
any upscale. Crop, don't shrink.

Two further rules, both learned the hard way in review:

1. **Captions must not wrap.** A wrapped caption gets its second line clipped by
   the caption bar — the same cropped-text defect as a bad crop.
2. **Crops land in whitespace, never through a label.** On the Odoo settings page
   the safe boundaries are `x=150` (the sidebar's right border), `x=556` (clear of
   the Google Calendar column) and `y=345` (below the last sidebar row).

`build_hero.py` implements all of this and is commented end to end — start there.

## What the hero shows

| Beat | Content | Source |
|---|---|---|
| 1/4 | Jitsi Configuration, switched off | capture, fsdemo17 |
| 2/4 | Ticked — the Company field appears, set to `Doodex` | capture, fsdemo17 |
| 3/4 | The room URL it produced | typographic panel; value read back by RPC from `calendar.event` id 8 |
| 4/4 | That room open on `meet.jit.si`, its name matching the Odoo token | screenshot supplied by the publisher |

Beat 3 is deliberately a design panel rather than a fake screenshot: no Odoo view
displays `jitsi_link`, so there was nothing to photograph. Beat 4 is cropped to
the join panel — the rest of that screenshot is an empty video stage, and the
mic/camera permission notice on it belongs to that machine, not the module.

The raw captures are kept in `shots/` so the hero can be re-cut without going
back to the server.

## Recording environment, for reference

`fsdemo17.doodex.net` · Odoo 17.0.1.3 · `appointment_jitsi` **17.0.1.0.0**
(unpatched). Left in place from the session: `is_jitsi_param=True`,
`company_param=4`, a company named exactly `Doodex` (id 4), and one meeting
`Doodex - Discovery call` (event id 8, 27 Aug 2026 09:00).

The `Doodex` company exists for one reason. On the **unpatched** module the room
URL interpolates the raw company name, so `My Company (San Francisco)` produced
`https://meet.jit.si/My Company (San Francisco)/My Company (San Francisco)-<token>`
— spaces, brackets, 119 characters, and a flat contradiction of Feature 02. With
`Doodex` it is
`https://meet.jit.si/Doodex/Doodex-5359c82930d34c5982902c7339788c37`. Apply patch E
and any company name slugifies on its own, at which point that company can go.

Two things about that server if you ever record there: the Settings form takes
35–40 s to render, and the Calendar view and `calendar.event` form would not
render at all — 40 s+, then blank, then a frozen renderer.

## Icons and QR codes — final, do not replace

`assets/icons/` holds 42 PNGs. `ic-*.png` are line icons rendered from SVG at six
times display size, so they stay sharp on retina; their intrinsic size is wrong on
purpose and they are sized by the CSS classes `.ajic-14` … `.ajic-30`, never by
`width`/`height`. Suffixes: `-v` violet, `-c` coral, `-w` white, `-g` green, `-r`
red — white on violet tiles and violet bands, coral on light surfaces.

`qr-*.png` are real scannable QR codes. They exist because the store invalidates
external links, so the QR image *is* the link:

| File | Encodes |
|---|---|
| `assets/icons/qr-meeting.png` | https://hub.doodex.net/r/meeting |
| `assets/icons/qr-whatsapp.png` | https://hub.doodex.net/r/whatsapp |
| `assets/icons/qr-mail.png` | mailto:odoo@doodex.net |
| `assets/icons/qr-blog.png` | https://www.doodex.net/en/blog/doodex-blog-2/appointment-jitsi-102 |

`build_assets.py` regenerates every icon in all five tones, so it emits far more
than the page uses — prune the unreferenced ones afterwards, as the delivery has
already been pruned.

## Rebuilding

```bash
python3 build_hero.py        # the hero GIF, from shots/
python3 build_assets.py      # icons + QR codes (regenerates all tones; prune after)
python3 build_preview.py     # preview + full compliance audit
```

Zero FAIL lines before the listing goes up.
