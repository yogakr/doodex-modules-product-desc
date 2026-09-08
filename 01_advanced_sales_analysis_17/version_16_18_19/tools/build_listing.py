#!/usr/bin/env python3
"""
build_listing.py - generate the Advanced Sales Analysis store listing for one or
more Odoo versions.

    python3 tools/build_listing.py            # writes 16.0, 18.0 and 19.0
    python3 tools/build_listing.py 19         # just one

One source, three outputs, so the three listings cannot drift apart. Everything
version-specific lives in VERSIONS below; the copy itself is version-neutral on
purpose - see NEUTRAL CLAIMS at the bottom of this docstring.

MARKUP RULES (from 07_personal_email_usage_17, which is the reference build)
  * Layout is real TABLE markup and depends on no stylesheet. No Bootstrap
    class anywhere: the store does not reliably serve Bootstrap to the
    description fragment, and without it every column collapses.
    table-layout:fixed gives equal columns, border-spacing is the gutter, with
    matching negative margins on the wrapper so cell edges line up with text.
    Where a block is a row of cards, THE CARD IS THE TD - cells in a row are
    the same height by definition.
  * Every rule that matters is an inline style using a property on Odoo's
    whitelist. The STYLE block carries hover/[open]/mobile only; delete it and
    the page is unchanged in substance.
  * Never write: background (shorthand), box-shadow, rgba(), display:grid/flex,
    gap, align-items, justify-content, position, overflow, transform,
    box-sizing, CSS variables, ::before/::after, @media in a style attribute.
  * No box-sizing anywhere, so no element carries both a width and a padding
    (the header/eyebrow shrink-to-fit cells use width:1px + nowrap, which is a
    sizing trick, not a box).
  * Responsive type is clamp(), which survives the sanitiser; @media cannot
    live in a style attribute.
  * Pure ASCII. The store serves the fragment with no charset, so a raw UTF-8
    byte is read as Windows-1252 and shows as mojibake. Write &mdash;, &rsquo;,
    &middot;, &rarr;, &times; - never the character.
  * Zero SCRIPT tags. The FAQ is a DETAILS accordion, and `open` is stripped
    under strict flags, so every summary reads correctly closed.
  * Ids are prefixed asa- because they land in the store page's own document.
  * Vendor guidelines: no external href. Other Doodex modules are root-relative
    /apps/modules/17.0/... paths. The QR cards carry NO href; their destination
    is printed beside them and encoded in the image, and the two must match
    byte for byte - the payloads are decoded and asserted in QR_PAYLOADS.

NEUTRAL CLAIMS
  The screenshots and GIFs in ./assets were captured on an Odoo 17 database and
  the automated test count was measured there. Rather than restate those as if
  they had been re-measured on 16, 18 and 19, the captions say "a live Odoo
  database" and the badge says "37 automated tests, shipped inside". Both are
  true on every version. If a per-version figure is ever measured, put it in
  VERSIONS and reference it from the badge.

Verify each output with:
    python3 tools/check_store_html.py <path to index.html>
It must come back with 0 errors.
"""
from __future__ import annotations

import os
import sys

# --------------------------------------------------------------------------
# version-specific values - the ONLY place a version number is written
# --------------------------------------------------------------------------
VERSIONS = {
    '16': {'v': '16.0', 'short': '16', 'module_version': '16.0.1.0.0'},
    '18': {'v': '18.0', 'short': '18', 'module_version': '18.0.1.0.0'},
    '19': {'v': '19.0', 'short': '19', 'module_version': '19.0.1.0.0'},
}

# The store listings for the other Doodex modules live under 17.0; linking a
# version that has no published listing would be a dead link, so these stay 17.0
# whatever version this page is built for.
XSELL_VERSION = '17.0'

# Decoded from the shipped PNGs. The text printed under each QR must equal the
# payload with the scheme stripped, because the guidelines do not allow the
# clickable link and a reader has to be able to type it.
QR_PAYLOADS = {
    'qr-meeting.png':  'https://hub.doodex.net/r/meeting',
    'qr-contact.png':  'https://doodex.net/contactus',
    'qr-whatsapp.png': 'https://hub.doodex.net/r/whatsapp',
}

# --------------------------------------------------------------------------
# design tokens (Doodex 2026)
# --------------------------------------------------------------------------
VIOLET   = '#270140'
CORAL    = '#fa7268'
CORAL_D  = '#e85c52'   # coral dark, for text on white
INK      = '#171717'
BODY     = '#525252'
MUTED    = '#737373'
LINE     = '#ece4f3'
TINT     = '#faf7fc'
TINT_2   = '#f4eef8'
WHITE    = '#ffffff'
ON_V_DIM = '#ad9eb6'
ON_V_MID = '#c7bdcd'
ON_V_LOW = '#8f7b9c'
ON_V_HI  = '#d4ccd9'
V_BORDER = '#887396'

FONT = ("'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "sans-serif")

WRAP = 1032          # content column
BAND = '56px 24px'   # full-width band padding

# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def band(inner: str, *, anchor: str = '', bg: str = WHITE,
         rules: str = '', pad: str = BAND, wrap: int = WRAP) -> str:
    """A full-width band with the 24px inset, holding a centred content column."""
    idattr = ' id="%s"' % anchor if anchor else ''
    style = 'background-color: %s; padding: %s' % (bg, pad)
    if rules:
        style += '; ' + rules
    return (
        '<div%s style="%s">\n'
        '   <div style="max-width: %dpx; margin: 0 auto; padding: 0">\n%s\n'
        '   </div>\n</div>\n' % (idattr, style, wrap, inner)
    )


def eyebrow(num: str, label: str) -> str:
    """The 02 / USE CASES rule that opens each section."""
    return (
        '<table class="lay" style="width: 100%%; border-collapse: collapse; '
        'border-spacing: 0px 0px; margin-bottom: 8px"><tbody><tr>\n'
        '   <td style="vertical-align: middle; width: 1px; white-space: nowrap; '
        'padding-right: 14px"><span style="font-size: 12px; font-weight: 800; '
        'color: %s; letter-spacing: 0.06em; margin-right: 14px">%s</span>'
        '<span style="font-size: 11.5px; font-weight: 800; letter-spacing: '
        '0.09em; text-transform: uppercase; color: %s">%s</span></td>\n'
        '   <td style="vertical-align: middle"><span style="display: block; '
        'height: 1px; background-color: %s"></span></td>\n'
        '</tr></tbody></table>\n' % (CORAL_D, num, MUTED, label, LINE)
    )


def h2(text: str, color: str = VIOLET) -> str:
    return ('<h2 style="color: %s; letter-spacing: -0.015em; margin: 0; '
            'font-weight: 800; font-size: clamp(23px, 2.7vw, 27px); '
            'line-height: 1.22">%s</h2>\n' % (color, text))


def lead(text: str, color: str = BODY, mt: str = '12px') -> str:
    return ('<p style="margin: %s 0 0; font-size: clamp(16.5px, 1.7vw, 18px); '
            'line-height: 1.6; color: %s; max-width: 760px">%s</p>\n'
            % (mt, color, text))


def kicker(text: str, color: str = CORAL, mb: str = '8px') -> str:
    return ('<p style="font-size: 11.5px; font-weight: 800; letter-spacing: '
            '0.09em; text-transform: uppercase; color: %s; margin: 0 0 %s">%s'
            '</p>\n' % (color, mb, text))


def diamond(color: str = CORAL, mr: str = '9px') -> str:
    return ('<span style="display: inline-block; width: 7px; height: 7px; '
            'background-color: %s; border-radius: 2px; margin-right: %s; '
            'vertical-align: middle"></span>' % (color, mr))


def icon_tile(src: str, size: int = 56, inner: int = 34,
              bg: str = TINT_2) -> str:
    """A rounded tile holding a PNG icon drawn at 132px and shown small."""
    pad = (size - inner) // 2
    return ('<span style="display: inline-block; width: %dpx; height: %dpx; '
            'border-radius: 10px; background-color: %s; text-align: center">'
            '<img src="./assets/icons/%s" alt="" width="132" height="132" '
            'style="max-width: 100%%; width: %dpx; height: %dpx; display: '
            'block; margin: %dpx auto"></span>'
            % (size, size, bg, src, inner, inner, pad))


def rows(cells: list[str], per_row: int, *, gutter_x: int = 24,
         gutter_y: int = 0, td_style: str = '', equal_height: bool = False,
         wrapper_margin: str = None) -> str:
    """Lay cells out in a fixed table, `per_row` to a row.

    The wrapper's negative margin cancels border-spacing so the outer cell
    edges line up with the surrounding text.
    """
    if wrapper_margin is None:
        wrapper_margin = '22px -%dpx 0' % gutter_x
    height = '; height: 1px' if equal_height else ''
    out = ['<div style="margin: %s">' % wrapper_margin,
           '<table class="lay" style="width: 100%%; table-layout: fixed; '
           'border-collapse: separate; border-spacing: %dpx %dpx%s"><tbody>'
           % (gutter_x, gutter_y, height)]
    for i in range(0, len(cells), per_row):
        chunk = list(cells[i:i + per_row])
        while len(chunk) < per_row:      # keep the fixed columns even
            chunk.append('')
        out.append('   <tr>')
        for c in chunk:
            style = td_style or 'vertical-align: top'
            if equal_height:
                style += '; height: 100%'
            out.append('      <td style="%s">%s</td>' % (style, c))
        out.append('   </tr>')
    out.append('</tbody></table>')
    out.append('</div>')
    return '\n'.join(out) + '\n'


def btn(label: str, href: str, *, kind: str = 'coral') -> str:
    if kind == 'coral':
        skin = ('background-color: %s; color: %s' % (CORAL, WHITE))
    elif kind == 'ghost-dark':
        skin = ('background-color: %s; color: %s; border-width: 1.5px; '
                'border-style: solid; border-color: %s' % (VIOLET, WHITE, V_BORDER))
    else:  # ghost-light
        skin = ('background-color: %s; color: %s; border-width: 1.5px; '
                'border-style: solid; border-color: %s' % (WHITE, VIOLET, VIOLET))
    return ('<a class="pbtn" href="%s" style="display: inline-block; %s; '
            'font-weight: 700; font-size: 15px; text-decoration: none; '
            'padding: 13px 24px; border-radius: 10px; line-height: 1.2; '
            'margin: 0 12px 12px 0">%s</a>' % (href, skin, label))


# --------------------------------------------------------------------------
# content - version-neutral
# --------------------------------------------------------------------------
MEASURES = [
    ('Amount Received', 'Cash in',
     'The share of each sales order line that has been invoiced and paid. '
     'Money in the bank, not a promise on a quotation.'),
    ('Waiting for Payment', 'Outstanding',
     'Invoiced, posted, and still unpaid. Your receivable, sitting on the '
     'sales report, without anyone opening Accounting to find it.'),
    ('Amount To Invoice', 'Unbilled',
     'Value you have committed to and not billed yet. Revenue you have '
     'already earned and not asked for &mdash; the line most companies '
     'forget to chase.'),
]

STEPS = [
    ('ic-how-install.png', 'Install it',
     'Add the module to your Odoo database from Apps. No menu, no wizard, no '
     'settings page &mdash; and every sales order you already have is counted '
     'during the install.'),
    ('ic-how-tick.png', 'Tick three measures',
     'Open <b>Sales &rarr; Reporting &rarr; Sales Analysis</b>, click '
     '<b>Measures</b>, and switch on Amount Received, Waiting for Payment and '
     'Amount To Invoice.'),
    ('ic-how-read.png', 'Read the cash',
     'The pivot fills in at once. Group by salesperson, customer, product or '
     'month and your sales report finally answers the only question that '
     'matters: was it paid?'),
]

USE_CASES = [
    ('uc-01-cash-by-salesperson.gif',
     '&ldquo;How much did we actually collect this quarter?&rdquo;',
     'Group the pivot by salesperson, then take <b>Amount Received</b> as the '
     'only measure. Two clicks, and the number on the row is cash collected, '
     'not commitments made.',
     'Cash collected per salesperson'),
    ('uc-02-receivable-by-customer.gif',
     '&ldquo;Who owes us money right now?&rdquo;',
     'Group by customer and measure <b>Waiting for Payment</b>. The customers '
     'with a figure in that column are your chase list, built from the sales '
     'report rather than from Accounting.',
     'The receivable chase list'),
    ('uc-03-invoicing-backlog.gif',
     '&ldquo;What have we delivered but not billed?&rdquo;',
     'Group by product category, measure <b>Amount To Invoice</b>. Anything '
     'sitting in that column is revenue you have earned and not asked for yet.',
     'The invoicing backlog'),
    ('uc-04-cash-timeline.gif',
     '&ldquo;What does the cash timeline look like?&rdquo;',
     'Group the date by week or month and put all three measures on. '
     'Collected, awaiting payment and not yet billed, side by side, period by '
     'period.',
     'Cash, week by week'),
]

FEATURES = [
    ('ic-feat-cash.png', 'Amount Received',
     'The part of the order line that has been invoiced and paid. Cash that '
     'actually arrived, not value that was billed.'),
    ('ic-feat-clock.png', 'Waiting for Payment',
     'Invoiced and posted, but the money has not landed. Your receivable gap, '
     'next to the order it came from.'),
    ('ic-feat-doc.png', 'Amount To Invoice',
     'Order value that has not been billed at all yet. The invoicing backlog, '
     'in money rather than in quantities.'),
    ('ic-feat-split.png', 'Part-paid invoices split in two',
     'An invoice paid halfway contributes to Amount Received and to Waiting '
     'for Payment at the same time, in proportion.'),
    ('ic-feat-layers.png', 'Down payments handled',
     'An advance invoice lands in Amount Received without counting the same '
     'money twice against the order lines.'),
    ('ic-feat-refresh.png', 'Credit notes subtract',
     'A customer credit note reduces Amount Received instead of being quietly '
     'left out of the total.'),
    ('ic-feat-globe.png', 'Converted line by line',
     'Each invoice line is converted into the currency of the sales order '
     'line before it is added up.'),
    ('ic-feat-filter.png', 'Follows the invoicing policy',
     'Orders invoiced on delivered quantity use the delivered figure, the '
     'same rule Odoo applies to its own amounts.'),
    ('ic-feat-shield.png', 'Line discounts respected',
     'Where an invoice line carries a different discount from the order line, '
     'the remainder is worked out from the invoice.'),
    ('ic-feat-pivot.png', 'Behaves like a standard measure',
     'Group, filter, compare periods, drill into a cell, export &mdash; the '
     'three measures do all of it, because they are ordinary measures.'),
    ('ic-feat-graph.png', 'Pivot and graph, both',
     'List, pivot and graph views all accept them. Nothing is limited to one '
     'view or one grouping.'),
    ('ic-feat-lock.png', 'Nothing leaves your database',
     'No external service, no outbound call, no telemetry. The figures are '
     'computed inside your own Odoo.'),
]

WHY = [
    ('The standard report knows what was invoiced, not what was '
     '<b>paid</b>.',
     'Odoo already gives you Untaxed Amount Invoiced and Untaxed Amount To '
     'Invoice. Neither of them knows whether the money arrived.'),
    ('Payment status lives in Accounting, not in Sales.',
     'Answering &ldquo;was it paid?&rdquo; today means leaving the report, '
     'opening Invoicing, and matching invoices to orders by hand.'),
    ('This splits invoiced value in two, and that split is the product.',
     '<b>Amount Received</b> is the part that was paid. <b>Waiting for '
     'Payment</b> is the part that was not. That distinction does not exist '
     'anywhere in the standard report.'),
    ('Amount To Invoice is recomputed so the three add up.',
     'It is line value minus what was received minus what is awaiting payment '
     '&mdash; so Received + Waiting + To Invoice returns the line total.'),
]

COMPARE = [
    ('Untaxed order value', True, True),
    ('Value already invoiced', True, True),
    ('Value not yet invoiced', True, True),
    ('Cash actually received', False, True),
    ('Invoiced but still unpaid', False, True),
    ('Part-paid invoice split across both', False, True),
    ('Down-payment aware', False, True),
    ('Credit-note aware', False, True),
    ('Something new for your team to learn', False, False),
]

REQS = [
    ('ic-req-version.png', 'Odoo version', '__ODOO_VERSION_REQ__'),
    ('ic-req-modules.png', 'Other apps needed',
     'Sales, Invoicing and Sales Management &mdash; all standard Odoo. '
     'Nothing external, nothing to buy alongside it.'),
    ('ic-req-server.png', 'Work on the server',
     'None. Install it from Apps like any other module. No command line, no '
     'extra software, no developer.'),
    ('ic-req-setup.png', 'Setup after installing',
     'None at all. There is no settings page, no menu and no wizard. Open '
     'Sales Analysis and the measures are in the list.'),
    ('ic-req-database.png', 'Your existing orders',
     'Counted too. The figures are computed and stored, so your history is '
     'filled in during installation, not just new orders.'),
    ('ic-req-money.png', 'Multi-currency',
     'Each invoice line is converted into the currency of the sales order '
     'line. These three columns are not passed through the report&rsquo;s own '
     'company-currency conversion, so read them as order-currency figures.'),
    ('ic-req-globe.png', 'Down-payment orders',
     'Advance invoices are recognised through Odoo&rsquo;s standard '
     '&ldquo;Down payment&rdquo; product name. If your database renames that '
     'product or runs in another language, tell us and we will adapt it for '
     'you.'),
    ('ic-req-user.png', 'Access rights',
     'Anyone who can already open Sales Analysis can use the measures. No new '
     'groups, no new permissions to hand out.'),
    ('ic-req-privacy.png', 'Your data',
     'Nothing leaves your Odoo. No external service, no outbound call, no '
     'telemetry. There is nothing in the module that talks to the internet.'),
    ('ic-req-bolt.png', 'Performance',
     'The figures are stored on the sales order line, so the report itself '
     'stays as quick as it is now. The one-off computation at install time is '
     'worth running out of hours on a very large database.'),
    ('ic-req-language.png', 'Language',
     'The module adds measure labels only, in English. There is no user '
     'interface to translate.'),
    ('ic-req-uninstall.png', 'If you ever remove it',
     'Uninstalling takes away the three measures and the stored fields behind '
     'them. Your orders, invoices and payments are untouched.'),
]

FAQ = [
    ('Where exactly do the three measures appear?',
     'In <b>Sales &rarr; Reporting &rarr; Sales Analysis</b>. Open the '
     '<b>Measures</b> dropdown and Amount Received, Waiting for Payment and '
     'Amount To Invoice are in the list beside the standard ones. The module '
     'adds no menu and no screen of its own.'),
    ('Odoo already has &ldquo;Untaxed Amount To Invoice&rdquo;. How is this '
     'different?',
     'The standard measure works from what has been <b>invoiced</b>. This '
     'module works from what has been <b>paid</b>. It splits invoiced value '
     'into Amount Received and Waiting for Payment, and then defines Amount '
     'To Invoice so the three add back up to the line. The payment split is '
     'the part that does not exist in the standard report.'),
    ('Is this a one-time purchase or a subscription?',
     'One time, for one database. There is no per-user fee, no per-order fee '
     'and nothing to renew or cancel.'),
    ('Do I need Odoo Enterprise?',
     'No. It only uses parts of Odoo that every Community install already '
     'has: Sales, Invoicing and Sales Management.'),
    ('Does it replace the standard Sales Analysis report?',
     'No, and that is deliberate. It extends the report you already use, so '
     'your saved filters, favourites and groupings keep working exactly as '
     'they do today.'),
    ('Will it count orders I already have, or only new ones?',
     'Existing ones too. The figures are computed and stored during '
     'installation, so your history is filled in. On a very large database it '
     'is worth installing outside business hours.'),
    ('What happens with a down payment?',
     'The advance is counted once, in the right column, instead of being '
     'double counted against the order lines. Down-payment invoices are '
     'recognised through Odoo&rsquo;s standard &ldquo;Down payment&rdquo; '
     'product name &mdash; if yours is renamed or in another language, tell '
     'us and we will adapt it.'),
    ('What about credit notes and partly paid invoices?',
     'A customer credit note reduces Amount Received rather than being left '
     'out. A partly paid invoice contributes to Amount Received and to '
     'Waiting for Payment at the same time, in proportion to what has been '
     'settled.'),
    ('Does it work with more than one currency?',
     'Yes. Each invoice line is converted into the currency of the sales '
     'order line before it is added up. Note that these three columns are not '
     'passed through the report&rsquo;s own company-currency conversion, so '
     'read them as order-currency figures.'),
    ('Is any of my data sent anywhere?',
     'No. There is no external service, no outbound call and no telemetry. '
     'Everything is computed inside your own Odoo, from records you already '
     'have.'),
    ('__FAQ_VERSIONS_Q__', '__FAQ_VERSIONS_A__'),
    ('Do I need a developer, and what if I uninstall it?',
     'No developer: install it from Apps like any other module, with nothing '
     'to configure afterwards. If you uninstall it, the three measures and '
     'the stored fields behind them go away and your orders, invoices and '
     'payments are untouched.'),
]

RELEASE_NOTES = [
    'Amount Received, Waiting for Payment and Amount To Invoice added as '
    'measures on the Sales Analysis report',
    'Payment split computed and stored on the sales order line, so the report '
    'stays fast',
    'Down-payment, credit-note and part-payment handling',
    'Per-line currency conversion into the sales order line&rsquo;s currency',
    '37 automated tests, shipped inside the module',
]

XSELL = [
    ('growth-suite-logo.png', 'Doodex Growth Suite', '$349 once',
     'Five CRM and marketing modules that do share one another&rsquo;s data: '
     'BizScan AI, Campaign Manager, Smart Dashboards, User Roles and '
     'Email&nbsp;Sync+. Sold as one suite.',
     'marketing_crm_automation_dashboard_campaign_doodex', True),
    ('flow-survey-reader-logo.png', 'Flow Survey Reader', 'Free',
     'Publish conditional surveys and forms straight from Odoo and keep every '
     'answer in your own database.',
     'flow_survey_reader', False),
    ('flow-survey-builder-logo.png', 'Flow Survey Builder', '$199 once',
     'The drag-and-drop editor for those surveys: 25 question types, slide '
     'branching and full theming.',
     'flow_survey', False),
]

CONTACT_CARDS = [
    ('ic-calendar-19.png', '30 minutes', 'Book a consultation',
     'See the measures running on your own Odoo data.',
     'qr-meeting.png', 'hub.doodex.net/r/meeting', True),
    ('ic-mail-19.png', 'Written reply', 'Send us a question',
     'Ask in writing and we answer by e-mail.',
     'qr-contact.png', 'doodex.net/contactus', False),
    ('ic-chat-19.png', 'Fastest reply', 'Chat on WhatsApp',
     'Reach the team on +62 821-3120-5030.',
     'qr-whatsapp.png', 'hub.doodex.net/r/whatsapp', False),
]


# --------------------------------------------------------------------------
# section renderers
# --------------------------------------------------------------------------
def sec_header(V) -> str:
    links = [('Overview', 'asa-overview'), ('Use Cases', 'asa-usecases'),
             ('Features', 'asa-features'), ('Why This', 'asa-why'),
             ('Requirements', 'asa-reqs'), ('FAQ', 'asa-faqs'),
             ('Releases', 'asa-releases')]
    jump = ''.join(
        '<a href="#%s" style="text-decoration: none; color: %s; font-size: '
        '13.5px; font-weight: 600; padding: 7px 13px; border-radius: 9999px; '
        'white-space: nowrap; display: inline-block; margin: 1px">%s</a>'
        % (a, INK, t) for t, a in links)
    return (
        '<div class="asahead" style="background-color: %s; border-bottom: 1px '
        'solid %s; padding: 12px 24px">\n'
        '   <div style="max-width: %dpx; margin: 0 auto; padding: 0">\n'
        '      <table class="lay" style="width: 100%%; border-collapse: '
        'collapse; border-spacing: 0px 0px"><tbody><tr>\n'
        '         <td style="vertical-align: middle; width: 1px; white-space: '
        'nowrap; padding-right: 18px"><a href="#asa-overview" style="'
        'text-decoration: none; color: %s; display: inline-block">'
        '<img src="./assets/icons/asa-icon.png" alt="Advanced Sales Analysis '
        'module icon" width="34" height="34" style="max-width: 100%%; width: '
        '34px; height: 34px; border-radius: 8px; display: inline-block; '
        'vertical-align: middle; margin-right: 11px"><span style="font-size: '
        '16px; font-weight: 800; color: %s; letter-spacing: -0.015em; '
        'white-space: nowrap; vertical-align: middle">Advanced Sales Analysis'
        '</span></a></td>\n'
        '         <td style="vertical-align: middle; text-align: center">'
        '<nav class="jumpwrap" style="display: inline-block; background-color: '
        '%s; border: 1px solid %s; border-radius: 9999px; padding: 4px">'
        '<span class="jump" style="display: inline-block">%s</span></nav></td>\n'
        '         <td style="vertical-align: middle; text-align: right; width: '
        '1px; white-space: nowrap; padding-left: 18px"><a class="pbtn" '
        'href="mailto:odoo@doodex.net?subject=Advanced%%20Sales%%20Analysis" '
        'style="display: inline-block; background-color: %s; color: %s; '
        'border-width: 1.5px; border-style: solid; border-color: %s; '
        'font-weight: 700; font-size: 13.5px; text-decoration: none; padding: '
        '10px 18px; border-radius: 10px; line-height: 1.2">Talk to Doodex</a>'
        '</td>\n'
        '      </tr></tbody></table>\n   </div>\n</div>\n'
        % (TINT, LINE, WRAP, VIOLET, VIOLET, WHITE, LINE, jump,
           WHITE, VIOLET, VIOLET)
    )


def sec_trustbar(V) -> str:
    chips = ['Odoo Official Partner',
             'Odoo %s &middot; Community &amp; Enterprise' % V['v'],
             '37 automated tests, shipped inside',
             'LGPL-3 &mdash; open source',
             'Depends on <b>base</b>, <b>sale</b>, <b>account</b>, '
             '<b>sale_management</b>']
    inner = '      ' + ''.join(
        '<span style="display: inline-block; font-size: 13px; font-weight: '
        '600; color: %s; background-color: %s; padding: 7px 15px; '
        'border-radius: 9999px; margin: 4px 4px">%s%s</span>'
        % (VIOLET, TINT_2, diamond(CORAL, '8px'), c) for c in chips)
    return band(inner, pad='32px 24px',
                rules='text-align: center').replace(
        'padding: 0">', 'padding: 0; text-align: center">')


def sec_hero(V) -> str:
    inner = (
        '      <div style="background-color: %s; border-radius: 20px; padding: '
        '52px 44px 46px">\n' % VIOLET
        + '         ' + kicker('Sales reporting for Odoo %s' % V['short'],
                                CORAL, '12px')
        + '         <p style="color: %s; font-size: 15px; max-width: 660px; '
          'margin: 0 0 6px; line-height: 1.6">Answering &ldquo;was this '
          'paid?&rdquo; means leaving Sales Analysis for Invoicing. It should '
          'mean ticking a box.</p>\n' % ON_V_DIM
        + '         <h1 style="color: %s; letter-spacing: -0.015em; margin: 0; '
          'font-weight: 800; font-size: clamp(32px, 4.4vw, 46px); line-height: '
          '1.1">Three cash measures inside your<br><span style="color: %s">'
          'Odoo Sales Analysis report.</span></h1>\n' % (WHITE, CORAL)
        + '         <p style="color: %s; font-size: clamp(16.5px, 1.7vw, 18px); '
          'line-height: 1.6; max-width: 660px; margin: 16px 0 0">Advanced '
          'Sales Analysis adds <b>Amount Received</b>, <b>Waiting for '
          'Payment</b> and <b>Amount To Invoice</b> to the Measures list of '
          'the report your team already opens. No new menu, no new screen, no '
          'setting to configure.</p>\n' % ON_V_HI
        + '         <div style="margin-top: 26px">\n            '
        + btn('See it in the report', '#asa-overview')
        + btn('Why not just the standard report?', '#asa-why', kind='ghost-dark')
        + btn('See the 12 behaviours', '#asa-features', kind='ghost-dark')
        + '\n         </div>\n'
        + '         <p style="color: %s; font-size: 12.5px; margin: 16px 0 0">'
          'LGPL-3, source included &middot; install from Apps and tick three '
          'measures &middot; odoo@doodex.net</p>\n' % ON_V_LOW
        + '      </div>'
    )
    return band(inner, pad='8px 24px 0')


def sec_hero_visual(V) -> str:
    inner = (
        '      <div style="background-color: %s; border: 1px solid %s; '
        'border-radius: 16px; padding: 18px">\n'
        '         <img src="./assets/screens/hero-measures-appear.gif" '
        'alt="The Measures dropdown of the Odoo Sales Analysis report, with '
        'Amount Received added as a new column" style="max-width: 100%%; '
        'width: 100%%; border-radius: 10px; display: block">\n'
        '      </div>\n'
        '      <p style="text-align: center; font-size: 12.5px; color: %s; '
        'margin: 12px 0 0">The standard Sales Analysis pivot on a live Odoo '
        'database &mdash; one new measure column per click.</p>'
        % (TINT, LINE, MUTED)
    )
    return band(inner, pad='24px 24px 8px')


def sec_overview(V) -> str:
    step_cards = []
    for i, (icon, title, body) in enumerate(STEPS, 1):
        step_cards.append(
            '<table style="width: 100%%; border-collapse: collapse; '
            'border-spacing: 0px 0px"><tbody><tr>\n'
            '   <td style="vertical-align: top; width: 56px; padding-right: '
            '16px">%s</td>\n'
            '   <td style="vertical-align: top">%s'
            '<h3 style="color: %s; letter-spacing: -0.015em; font-weight: 800; '
            'font-size: 16px; margin: 2px 0 6px">%s</h3>'
            '<p style="font-size: 13.5px; color: %s; margin: 0; line-height: '
            '1.6">%s</p></td>\n'
            '</tr></tbody></table>'
            % (icon_tile(icon), kicker('Step %d' % i, CORAL_D, '6px'),
               VIOLET, title, MUTED, body))

    measure_rows = []
    for name, tag, body in MEASURES:
        measure_rows.append(
            '<div style="border-top: 1px solid %s; padding: 18px 0 0">'
            '<h3 style="margin: 0 0 6px; font-size: 17px; font-weight: 800; '
            'color: %s; letter-spacing: -0.015em; display: inline-block; '
            'margin-right: 10px">%s</h3>'
            '<span style="display: inline-block; font-size: 10px; font-weight: '
            '800; letter-spacing: 0.07em; text-transform: uppercase; '
            'background-color: %s; color: %s; padding: 4px 9px; border-radius: '
            '9999px; vertical-align: middle">%s</span>'
            '<p style="margin: 4px 0 18px; font-size: 14px; color: %s; '
            'line-height: 1.65">%s</p></div>'
            % (LINE, VIOLET, name, TINT_2, CORAL_D, tag, BODY, body))

    equation = (
        '      <div style="background-color: %s; border-radius: 16px; padding: '
        '26px 28px; text-align: center">\n'
        '         <p style="margin: 0; font-size: clamp(15px, 1.9vw, 19px); '
        'font-weight: 800; color: %s; line-height: 1.5">Amount Received'
        '<span style="color: %s; margin: 0 10px">+</span>Waiting for Payment'
        '<span style="color: %s; margin: 0 10px">+</span>Amount To Invoice'
        '<span style="color: %s; margin: 0 10px">=</span>'
        '<span style="color: %s">the line&rsquo;s untaxed total</span></p>\n'
        '         <p style="margin: 12px auto 0; font-size: 13.5px; color: %s; '
        'line-height: 1.6; max-width: 620px">So every row reconciles. '
        'Part-paid invoices, down payments and credit notes are all handled, '
        'which is the part a spreadsheet built by hand always gets wrong.</p>\n'
        '      </div>' % (VIOLET, WHITE, CORAL, CORAL, CORAL, CORAL, ON_V_MID)
    )

    inner = (
        '      ' + eyebrow('01', 'Overview')
        + '      ' + h2('Nothing new to learn. The report you already open, '
                        'with three more measures.')
        + '      ' + lead('Three stored measures on the Odoo Sales Analysis '
                          'report your team already uses &mdash; no second '
                          'dashboard to keep in sync, no data to re-enter, no '
                          'new screen to learn.')
        + rows(step_cards, 3, gutter_x=24,
               td_style='vertical-align: top; padding: 24px 0 0; border-top: '
                        '1px solid ' + LINE)
        + '      <div style="margin-top: 34px">' + kicker(
            'What each measure counts', CORAL_D, '14px')
        + ''.join(measure_rows) + '</div>\n'
        + equation
    )
    return band(inner, anchor='asa-overview')


def _contact_card(n, card) -> str:
    icon, tag, title, body, qr, printed, first = card
    payload = QR_PAYLOADS[qr]
    assert payload.split('//', 1)[1] == printed, (payload, printed)
    border = ('border-width: 2px; border-style: solid; border-color: %s'
              % CORAL) if first else (
              'border-width: 1px; border-style: solid; border-color: %s' % LINE)
    footer_skin = ('background-color: %s; color: %s' % (CORAL, WHITE)) if first \
        else ('background-color: %s; color: %s' % (TINT, VIOLET))
    return (
        '<table style="width: 100%%; height: 100%%; border-collapse: collapse; '
        'border-spacing: 0px 0px"><tbody>\n'
        '   <tr><td style="vertical-align: top; padding: 16px 16px 0">\n'
        '      <table style="width: 100%%; border-collapse: collapse; '
        'border-spacing: 0px 0px"><tbody><tr>\n'
        '         <td style="vertical-align: middle; width: 30px">%s</td>\n'
        '         <td style="vertical-align: middle; text-align: right">'
        '<span style="display: inline-block; font-size: 10px; font-weight: '
        '800; letter-spacing: 0.07em; text-transform: uppercase; '
        'background-color: %s; color: %s; padding: 4px 9px; border-radius: '
        '9999px">%s</span></td>\n'
        '      </tr></tbody></table>\n'
        '      <h3 style="font-size: 15.5px; color: %s; font-weight: 800; '
        'letter-spacing: -0.015em; margin: 9px 0 0">%s</h3>\n'
        '      <p style="font-size: 12.5px; line-height: 1.5; color: %s; '
        'margin: 6px 0 0">%s</p>\n'
        '   </td></tr>\n'
        '   <tr><td style="vertical-align: bottom; padding: 12px 16px 16px">\n'
        '      <span style="display: block; background-color: %s; '
        'border-radius: 10px; padding: 10px; text-align: center">'
        '<img src="./assets/icons/%s" alt="QR code for %s" width="98" '
        'height="98" style="max-width: 98px; display: block; width: 100%%; '
        'height: auto; margin: 0 auto"></span>\n'
        '      <span style="display: block; %s; font-weight: 700; font-size: '
        '13px; padding: 9px 10px; border-radius: 10px; text-align: center; '
        'margin-top: 10px">%s</span>\n'
        '   </td></tr>\n'
        '</tbody></table>'
        % (icon_tile(icon, 30, 19, VIOLET), CORAL, WHITE, tag,
           VIOLET, title, MUTED, body, TINT, qr, printed, footer_skin, printed)
    ), border


def sec_cta(V, n, kicker_text, heading, body) -> str:
    cells, borders = [], []
    for i, card in enumerate(CONTACT_CARDS):
        html, border = _contact_card(i, card)
        cells.append(html)
        borders.append(border)
    tds = ''.join(
        '      <td style="vertical-align: top; height: 100%%; '
        'background-color: %s; border-radius: 14px; %s">%s</td>\n'
        % (WHITE, borders[i], cells[i]) for i in range(len(cells)))
    inner = (
        '      <div style="background-color: %s; border-radius: 20px; padding: '
        '28px 28px 22px">\n' % VIOLET
        + '         <div style="max-width: 660px">\n            '
        + kicker(kicker_text, CORAL, '8px')
        + '            <h2 style="color: %s; letter-spacing: -0.015em; '
          'font-weight: 800; font-size: clamp(21px, 2.4vw, 24px); line-height: '
          '1.25; margin: 0 0 8px">%s</h2>\n' % (WHITE, heading)
        + '            <p style="color: %s; font-size: 14.5px; line-height: '
          '1.55; margin: 0">%s</p>\n' % (ON_V_MID, body)
        + '         </div>\n'
        + '         <div style="margin: 8px -14px -14px">\n'
          '         <table class="lay" style="width: 100%; table-layout: '
          'fixed; border-collapse: separate; border-spacing: 14px 14px; '
          'height: 1px"><tbody><tr>\n' + tds
        + '         </tr></tbody></table>\n         </div>\n'
        + '         <p style="color: %s; font-size: 12px; margin: 16px 0 0; '
          'text-align: center">Scan a code with your phone. The address '
          'printed under each code is the address the code contains, so you '
          'can type it in instead.</p>\n' % ON_V_LOW
        + '      </div>'
    )
    return band(inner, pad='32px 24px')


def sec_usecases(V) -> str:
    cards = []
    for gif, q, body, cap in USE_CASES:
        cards.append(
            '<h3 style="color: %s; letter-spacing: -0.015em; font-weight: 800; '
            'font-size: 16px; margin: 0 0 8px">%s</h3>'
            '<p style="font-size: 13.5px; color: %s; margin: 0 0 12px; '
            'line-height: 1.6">%s</p>'
            '<img src="./assets/gifs/%s" alt="%s" style="max-width: 100%%; '
            'width: 100%%; border-radius: 10px; display: block">'
            '<p style="font-size: 12px; color: %s; margin: 10px 0 0">%s%s</p>'
            % (VIOLET, q, MUTED, body, gif, cap, MUTED,
               diamond(CORAL, '8px'), cap))
    inner = (
        '      ' + eyebrow('02', 'Use Cases')
        + '      ' + h2('Four questions it answers without leaving the report')
        + '      ' + lead('These are not features. They are the questions '
                          'people actually ask on a Monday morning, and the '
                          'clicks that answer them.')
        + rows(cards, 2, gutter_x=24, gutter_y=24,
               td_style='vertical-align: top; background-color: ' + WHITE
                        + '; border: 1px solid ' + LINE
                        + '; border-radius: 14px; padding: 20px',
               equal_height=True)
    )
    return band(inner, anchor='asa-usecases', bg=TINT,
                rules='border-top: 1px solid %s; border-bottom: 1px solid %s'
                      % (LINE, LINE))


def sec_features(V) -> str:
    cards = []
    for icon, title, body in FEATURES:
        cards.append(
            '<table style="width: 100%%; border-collapse: collapse; '
            'border-spacing: 0px 0px"><tbody><tr>\n'
            '   <td style="vertical-align: top; width: 44px; padding-right: '
            '14px">%s</td>\n'
            '   <td style="vertical-align: top">'
            '<h3 style="color: %s; letter-spacing: -0.015em; font-weight: 800; '
            'font-size: 15px; margin: 0 0 5px">%s</h3>'
            '<p style="font-size: 13px; color: %s; margin: 0; line-height: '
            '1.6">%s</p></td>\n'
            '</tr></tbody></table>'
            % (icon_tile(icon, 44, 26), VIOLET, title, MUTED, body))
    inner = (
        '      ' + eyebrow('03', 'Features')
        + '      ' + h2('Twelve things it does, stated plainly')
        + '      ' + lead('The module adds three measures and the arithmetic '
                          'behind them. That is the whole scope &mdash; and '
                          'the awkward cases are the reason it exists.')
        + rows(cards, 3, gutter_x=24, gutter_y=24,
               td_style='vertical-align: top; padding: 20px 0 0; border-top: '
                        '1px solid ' + LINE)
    )
    return band(inner, anchor='asa-features')


def sec_why(V) -> str:
    points = []
    for i, (head, body) in enumerate(WHY, 1):
        points.append(
            '<div style="border-top: 1px solid %s; padding: 20px 0 0">'
            '<table style="width: 100%%; border-collapse: collapse; '
            'border-spacing: 0px 0px"><tbody><tr>'
            '<td style="vertical-align: top; width: 30px; padding-right: 14px">'
            '<span style="display: inline-block; width: 30px; height: 30px; '
            'border-radius: 9px; background-color: %s; color: %s; font-size: '
            '13px; font-weight: 800; text-align: center; line-height: 30px">'
            '%d</span></td>'
            '<td style="vertical-align: top">'
            '<h3 style="color: %s; letter-spacing: -0.015em; font-weight: 800; '
            'font-size: 16px; margin: 2px 0 6px">%s</h3>'
            '<p style="font-size: 13.5px; color: %s; margin: 0 0 18px; '
            'line-height: 1.6">%s</p></td>'
            '</tr></tbody></table></div>'
            % (LINE, VIOLET, WHITE, i, VIOLET, head, MUTED, body))

    tick = ('<img src="./assets/icons/ic-check-13.png" alt="yes" width="13" '
            'height="13" style="max-width: 100%; width: 13px; height: 13px; '
            'display: inline-block; vertical-align: middle">')
    cross = ('<span style="display: inline-block; color: %s; font-size: 15px; '
             'font-weight: 700; line-height: 1">&times;</span>' % '#b9a8c4')
    trows = [
        '         <tr><td style="vertical-align: middle; padding: 12px 0; '
        'border-bottom: 1px solid %s; font-size: 13.5px; color: %s">What the '
        'report can tell you</td>'
        '<td style="vertical-align: middle; padding: 12px 0; border-bottom: '
        '1px solid %s; text-align: center; font-size: 11.5px; font-weight: '
        '800; letter-spacing: 0.06em; text-transform: uppercase; color: %s">'
        'Standard</td>'
        '<td style="vertical-align: middle; padding: 12px 0; border-bottom: '
        '1px solid %s; text-align: center; font-size: 11.5px; font-weight: '
        '800; letter-spacing: 0.06em; text-transform: uppercase; color: %s">'
        '+ Advanced</td></tr>' % (LINE, MUTED, LINE, MUTED, LINE, CORAL_D)]
    for label, std, adv in COMPARE:
        trows.append(
            '         <tr><td style="vertical-align: middle; padding: 11px 0; '
            'border-bottom: 1px solid %s; font-size: 13.5px; color: %s">%s</td>'
            '<td style="vertical-align: middle; padding: 11px 0; '
            'border-bottom: 1px solid %s; text-align: center">%s</td>'
            '<td style="vertical-align: middle; padding: 11px 0; '
            'border-bottom: 1px solid %s; text-align: center">%s</td></tr>'
            % (LINE, BODY, label, LINE, tick if std else cross,
               LINE, tick if adv else cross))
    table = (
        '      <div style="margin-top: 30px; background-color: %s; border: 1px '
        'solid %s; border-radius: 16px; padding: 8px 22px 14px">\n'
        '      <table style="width: 100%%; border-collapse: collapse; '
        'border-spacing: 0px 0px"><tbody>\n%s\n      </tbody></table>\n'
        '      <p style="font-size: 12.5px; color: %s; margin: 14px 0 0; '
        'line-height: 1.6">Both columns are a cross on the last row, on '
        'purpose. Adding a menu would have been the easy way to make this '
        'module look bigger, and it would also have given your team a new '
        'screen to learn. It adds neither.</p>\n      </div>'
        % (WHITE, LINE, '\n'.join(trows), MUTED)
    )
    inner = (
        '      ' + eyebrow('04', 'Why This')
        + '      ' + h2('&ldquo;Odoo already has a Sales Analysis report. Why '
                        'buy this?&rdquo;')
        + '      ' + lead('A fair question, and the honest answer is narrow: '
                          'the standard report is missing one dimension, and '
                          'this adds exactly that one.')
        + '      <div style="margin-top: 24px">' + ''.join(points) + '</div>\n'
        + table
    )
    return band(inner, anchor='asa-why', bg=TINT,
                rules='border-top: 1px solid %s; border-bottom: 1px solid %s'
                      % (LINE, LINE))


def sec_reqs(V) -> str:
    cards = []
    for icon, title, body in REQS:
        body = body.replace('__ODOO_VERSION_REQ__',
                            'Odoo %s, Community or Enterprise. You do not need '
                            'an Enterprise licence.' % V['v'])
        cards.append(
            '<table style="width: 100%%; border-collapse: collapse; '
            'border-spacing: 0px 0px"><tbody><tr>\n'
            '   <td style="vertical-align: top; width: 40px; padding-right: '
            '13px">%s</td>\n'
            '   <td style="vertical-align: top">'
            '<h3 style="color: %s; letter-spacing: -0.015em; font-weight: 800; '
            'font-size: 14.5px; margin: 0 0 5px">%s</h3>'
            '<p style="font-size: 13px; color: %s; margin: 0; line-height: '
            '1.6">%s</p></td>\n'
            '</tr></tbody></table>'
            % (icon_tile(icon, 40, 24), VIOLET, title, MUTED, body))

    specs = [('Licence', 'LGPL-3 &mdash; open source, source included'),
             ('Odoo version', V['v']),
             ('Category', 'Sales'),
             ('Technical name', 'advanced_sales_analysis'),
             ('Author and maintainer', 'Doodex'),
             ('Depends on', 'base, sale, account, sale_management')]
    srows = ''.join(
        '         <tr><td style="vertical-align: middle; padding: 11px 0; '
        'border-bottom: 1px solid %s; font-size: 13px; color: %s; width: 38%%">'
        '%s</td><td style="vertical-align: middle; padding: 11px 0; '
        'border-bottom: 1px solid %s; font-size: 13px; font-weight: 700; '
        'color: %s">%s</td></tr>\n' % (LINE, MUTED, k, LINE, VIOLET, v)
        for k, v in specs)
    spec_block = (
        ('      <div style="margin-top: 30px; background-color: %s; '
         'border-radius: 16px; padding: 8px 22px 16px">\n' % TINT)
        + '      ' + kicker('Specifications', CORAL_D, '0')
        + ('      <table style="width: 100%; border-collapse: collapse; '
           'border-spacing: 0px 0px"><tbody>\n')
        + srows
        + '      </tbody></table>\n      </div>'
    )
    inner = (
        '      ' + eyebrow('05', 'Requirements')
        + '      ' + h2('What it needs, and what it does not')
        + '      ' + lead('Including the parts that are limitations. You '
                          'should know them before you install it, not after.')
        + rows(cards, 3, gutter_x=24, gutter_y=24,
               td_style='vertical-align: top; padding: 20px 0 0; border-top: '
                        '1px solid ' + LINE)
        + spec_block
    )
    return band(inner, anchor='asa-reqs')


def sec_faq(V) -> str:
    q_versions = ('Which Odoo versions are supported?',
                  'This is the Odoo %s edition, and this page describes that '
                  'build. Advanced Sales Analysis is published separately for '
                  'other supported Odoo versions &mdash; if you run a version '
                  'you cannot find on the store, write to us and we will tell '
                  'you honestly where that build stands rather than sell you '
                  'the wrong one.' % V['v'])
    items = []
    for q, a in FAQ:
        if q == '__FAQ_VERSIONS_Q__':
            q, a = q_versions
        items.append(
            '      <details class="faq" style="border-top: 1px solid %s">'
            '<summary style="display: block; padding: 16px 30px 16px 0">'
            '<span style="font-size: 20px; font-weight: 700; color: %s; float: '
            'right; margin-left: 16px; line-height: 1.25">+</span>'
            '<span style="display: block; font-size: 15.5px; font-weight: 700; '
            'color: %s; line-height: 1.4">%s</span></summary>'
            '<div style="padding: 0 30px 18px 0"><p style="margin: 0; '
            'font-size: 14px; color: %s; line-height: 1.65">%s</p></div>'
            '</details>' % (LINE, CORAL_D, VIOLET, q, BODY, a))
    inner = (
        '      ' + eyebrow('06', 'FAQ')
        + '      ' + h2('Twelve real questions')
        + '      ' + lead('The ones we are actually asked, answered without '
                          'marketing language.')
        + '      <div style="margin-top: 22px">\n' + '\n'.join(items)
        + '\n      </div>'
    )
    return band(inner, anchor='asa-faqs', bg=TINT, wrap=772,
                rules='border-top: 1px solid %s; border-bottom: 1px solid %s'
                      % (LINE, LINE))


def sec_xsell(V) -> str:
    cells = []
    for logo, name, price, body, tech, dark in XSELL:
        title_c = WHITE if dark else VIOLET
        body_c = ON_V_MID if dark else MUTED
        chip_bg = CORAL if dark else TINT_2
        chip_c = WHITE if dark else VIOLET
        link_skin = (f'background-color: {CORAL}; color: {WHITE}' if dark else
                     f'background-color: {WHITE}; color: {VIOLET}; '
                     f'border-width: 1px; border-style: solid; '
                     f'border-color: {LINE}')
        cells.append(
            '<table style="width: 100%; height: 100%; border-collapse: '
            'collapse; border-spacing: 0px 0px"><tbody>\n'
            '   <tr><td style="vertical-align: top; padding: 20px 20px 0">\n'
            '      <table style="width: 100%; border-collapse: collapse; '
            'border-spacing: 0px 0px"><tbody><tr>\n'
            '         <td style="vertical-align: middle; width: 34px">'
            f'<img src="./assets/icons/{logo}" alt="" width="34" height="34" '
            'style="max-width: 100%; width: 34px; height: 34px; display: '
            'block"></td>\n'
            '         <td style="vertical-align: middle; text-align: right">'
            '<span style="display: inline-block; font-size: 10px; '
            'font-weight: 800; letter-spacing: 0.07em; text-transform: '
            f'uppercase; background-color: {chip_bg}; color: {chip_c}; '
            f'padding: 4px 9px; border-radius: 9999px">{price}</span></td>\n'
            '      </tr></tbody></table>\n'
            f'      <h3 style="font-size: 15.5px; color: {title_c}; '
            'font-weight: 800; letter-spacing: -0.015em; margin: 12px 0 0">'
            f'{name}</h3>\n'
            f'      <p style="font-size: 12.5px; line-height: 1.55; '
            f'color: {body_c}; margin: 6px 0 0">{body}</p>\n'
            '   </td></tr>\n'
            '   <tr><td style="vertical-align: bottom; padding: 14px 20px '
            '20px">'
            f'<a class="pbtn" href="/apps/modules/{XSELL_VERSION}/{tech}" '
            f'style="display: inline-block; {link_skin}; font-weight: 700; '
            'font-size: 12.5px; text-decoration: none; padding: 9px 14px; '
            'border-radius: 9px; line-height: 1.2">Open on the Apps Store '
            '&rarr;</a></td></tr>\n'
            '</tbody></table>')

    tds = ''
    for i, cell in enumerate(cells):
        dark = XSELL[i][5]
        tds += (f'      <td style="vertical-align: top; height: 100%; '
                f'background-color: {VIOLET if dark else WHITE}; '
                f'border-radius: 14px; border-width: 1px; border-style: '
                f'solid; border-color: {VIOLET if dark else LINE}">'
                f'{cell}</td>\n')

    inner = (
        '      <div style="text-align: center">'
        + kicker('Works great with', CORAL_D, '10px')
        + '      ' + h2('Other Doodex modules, built the same way')
        + f'      <p style="margin: 12px auto 0; font-size: clamp(16.5px, '
          f'1.7vw, 18px); line-height: 1.6; color: {BODY}; max-width: 700px">'
          'Different problems, same approach: narrow scope, a one-time price '
          'and the limits stated up front. Each one installs on its own.</p>\n'
        + '      </div>\n'
        + '      <div style="margin: 22px -14px 0">\n'
          '      <table class="lay" style="width: 100%; table-layout: fixed; '
          'border-collapse: separate; border-spacing: 14px 14px; '
          'height: 1px"><tbody><tr>\n'
        + tds
        + '      </tr></tbody></table>\n      </div>'
    )
    return band(inner, bg=TINT, rules=f'border-top: 1px solid {LINE}')


def sec_releases(V) -> str:
    notes = ''.join(
        '<p style="margin: 0 0 7px; font-size: 13.5px; color: %s; line-height: '
        '1.6">%s%s</p>' % (MUTED, diamond(CORAL, '9px'), n)
        for n in RELEASE_NOTES)
    inner = (
        '      ' + eyebrow('07', 'Releases')
        + '      ' + h2('Public release history')
        + '      ' + lead('Every release is listed here with what changed. If '
                          'a version is not on this list, it does not exist.')
        + '      <div style="margin-top: 24px; border-left-width: 2px; '
          'border-left-style: solid; border-left-color: %s; '
          'padding-left: 22px">\n'
          '         <span style="display: block; width: 11px; height: 11px; '
          'border-radius: 4px; background-color: %s; margin-left: -28px"></span>'
          '\n'
          '         <p style="margin: 6px 0 10px"><span style="font-size: '
          '15.5px; font-weight: 800; color: %s; margin-right: 10px">%s</span>'
          '<span style="display: inline-block; font-size: 10px; font-weight: '
          '800; letter-spacing: 0.07em; text-transform: uppercase; '
          'background-color: %s; color: %s; padding: 4px 9px; border-radius: '
          '9999px; vertical-align: middle; margin-right: 10px">New</span>'
          '<span style="font-size: 13.5px; color: %s">First public release for '
          'Odoo %s</span></p>\n'
          '         %s\n'
          '      </div>'
          % (LINE, CORAL, VIOLET, V['module_version'], TINT_2, VIOLET,
             MUTED, V['v'], notes)
    )
    return band(inner, anchor='asa-releases')


# --------------------------------------------------------------------------
STYLE_BLOCK = """<style>
/* ==========================================================================
   NOT LOAD-BEARING. Everything that matters is in a style attribute using
   properties on Odoo's whitelist, including the whole layout, which is real
   table markup. Delete this element and the page is unchanged in substance
   - tools/check_store_html.py performs exactly that test.

   What lives here is progressive enhancement only:
     * hover and [open] states, which cannot be inlined at all;
     * the mobile collapse, which turns the layout tables into a single
       column under 820px. On a phone with this block killed the tables stay
       side by side and get narrow, which is legible but tight.

   NO box-sizing rule on purpose: the store kills this block, so any element
   that set both a size and a border would change size between preview and
   store.
   ========================================================================== */
.asa img { max-width: 100%; }

/* hover / open states */
.asa .jump a:hover { background-color: __TINT2__; color: __VIOLET__; }
.asa .pbtn { transition: opacity .15s ease; }
.asa .pbtn:hover { opacity: .9; }
.asa .mini:hover { text-decoration: underline; }
.asa .faq > summary:hover span { color: __CORALD__; }
.asa .faq > summary { list-style: none; cursor: pointer; }
.asa .faq > summary::-webkit-details-marker { display: none; }
.asa .faq > summary::marker { content: ""; }
.asa details.faq[open] > summary > span:first-child { color: __VIOLET__; }

/* mobile: unstack the layout tables */
@media (max-width: 820px) {
   .asa table.lay,
   .asa table.lay tbody,
   .asa table.lay tr,
   .asa table.lay td { display: block !important; width: auto !important; }
   .asa table.lay td { margin-bottom: 14px; }
   .asa table.lay td:empty { display: none !important; }
}
</style>"""

HEADER_COMMENT = """<!-- ==========================================================================
  Advanced Sales Analysis - Odoo Apps Store listing description
  Odoo __V__ | module version __MODVER__ | LGPL-3 | Doodex

  GENERATED FILE. Edit tools/build_listing.py and run it again; do not patch
  this file by hand, or the __V__ / other editions will drift apart.
      python3 tools/build_listing.py

  NO PRICE ANYWHERE IN THIS PAGE, deliberately. The store renders the price
  from __manifest__.py next to the Buy button; any figure here would be a
  second copy with nothing keeping the two in step.
  Technical name: advanced_sales_analysis

  PASTE TARGET: the "Description" field of the Odoo Apps Store upload, and the
  file advanced_sales_analysis/static/description/index.html in the module.
  Upload ./assets, folders and all, next to this file. Nothing here loads an
  image from anywhere else, and nothing here loads a stylesheet or a script.

  HOW THIS FILE IS BUILT
  ----------------------
  The store runs odoo.tools.mail.html_sanitize() over the description. It
  deletes the head, STYLE and SCRIPT elements, and it may also delete every
  inline CSS property outside its own whitelist. This page is written for that
  worst case.

   * LAYOUT IS REAL TABLE MARKUP and depends on no stylesheet at all. There is
     not one Bootstrap class on this page: the store does not reliably serve
     Bootstrap to the description fragment, and without it every multi-column
     block collapses into one column and the gutters vanish.
     table-layout:fixed gives equal columns, border-spacing is the gutter, with
     matching negative margins on the wrapper so the outer cell edges still
     line up with the text. Where a block is a row of cards THE CARD IS THE TD,
     because cells in a row are the same height by definition.
   * NOTHING DEPENDS ON THE STYLE BLOCK. Every rule that matters is written
     inline using whitelisted properties only.
     NEVER write, they are silently removed:
       background (shorthand!)     -> background-color
       box-shadow                  -> border-width / border-style / border-color
       border-left / border-right  -> border-left-width / -style / -color
       rgba(...)                   -> a solid hex mixed against its own ground
       display:grid / flex, gap, align-items, justify-content, flex-*
                                   -> a real TABLE, see above
       position / top / left       -> restructure, or bake it into the image
       transform, overflow, cursor, box-sizing, CSS variables,
       ::before / ::after, @media  -> dropped, no equivalent
   * NO box-sizing ANYWHERE, so no element carries both a width and a padding.
     The content column is 1032px wide and the 24px inset sits on the
     full-width band around it.
   * RESPONSIVE TYPE IS clamp(), not @media - a media query cannot live in a
     style attribute, but a clamp() value passes through the sanitiser intact.
   * ZERO SCRIPT tags. The FAQ is a DETAILS accordion. Note `open` is NOT a
     safe attribute and is stripped under strict flags, so every summary reads
     correctly closed.
   * PURE ASCII. The store serves the fragment with no charset of its own, so a
     raw UTF-8 character is read as Windows-1252 and shown as mojibake. Write
     &mdash; and &middot;, never the character itself.
   * LINKS ARE CONSTRAINED BY THE VENDOR GUIDELINES. Only static/description
     resources, canonical YouTube, Microsoft Teams, mailto: and skype: survive.
     The other Doodex modules are linked as root-relative /apps/modules/17.0/
     paths - that is where their listings actually are, whatever version this
     page is built for. The booking, contact and WhatsApp cards carry NO href;
     their destination is printed beside them and encoded in the QR image, and
     build_listing.py asserts the printed text equals the decoded QR payload.
   * VERSION-NEUTRAL PROOF. The screenshots and GIFs were captured on an Odoo
     17 database and the test count was measured there, so the captions say
     "a live Odoo database" and the badge says "37 automated tests, shipped
     inside". Both are true on every version. Do not restate a figure per
     version unless it has actually been measured on that version.
   * IDS ARE PREFIXED asa- because they land in the store page's own document.

  Verify every change with:  python3 tools/check_store_html.py <this file>
  It must come back with 0 errors.
========================================================================== -->"""


def build(key: str) -> str:
    V = VERSIONS[key]
    style = (STYLE_BLOCK.replace('__TINT2__', TINT_2)
             .replace('__VIOLET__', VIOLET).replace('__CORALD__', CORAL_D))
    head_comment = (HEADER_COMMENT.replace('__V__', V['v'])
                    .replace('__MODVER__', V['module_version']))
    parts = [
        sec_header(V), sec_trustbar(V), sec_hero(V), sec_hero_visual(V),
        sec_overview(V),
        sec_cta(V, 1, 'Before you install it',
                'Get a straight answer about this module',
                'Ask whether it fits your Odoo, what the three measures would '
                'show on your own data, or whether the arithmetic matches your '
                'accounting rules. A real person replies.'),
        sec_usecases(V), sec_features(V), sec_why(V),
        sec_cta(V, 2, 'Run it on your numbers',
                'See the three measures on your own data',
                'Bring a copy of your database or a screen-share of the report '
                'you use today, and we will show you what the three columns '
                'say about your own orders.'),
        sec_reqs(V), sec_faq(V), sec_xsell(V), sec_releases(V),
        sec_cta(V, 3, 'Ready when you are',
                'Put the payment side into your sales report',
                'Install it, open Sales Analysis and tick three measures '
                '&mdash; there is no settings page and nothing to configure. '
                'If you would rather see it first, book the consultation and '
                'we will run it on your own data.'),
    ]
    body = '\n'.join(parts)
    return (
        '<!DOCTYPE html>\n<html lang="en"><head>\n'
        '      <meta charset="UTF-8">\n'
        '      <meta name="viewport" content="width=device-width, '
        'initial-scale=1.0">\n'
        '      <title>Advanced Sales Analysis for Odoo %s &mdash; cash '
        'measures on the Sales Analysis report</title>\n'
        '      <meta name="description" content="Add Amount Received, Waiting '
        'for Payment and Amount To Invoice as measures on the Odoo %s Sales '
        'Analysis report. LGPL-3, open source, no new menus, nothing to '
        'configure. By Doodex.">\n'
        '   </head>\n   <body>\n%s\n'
        '<div class="asa" style="background-color: %s; color: %s; '
        'font-family: %s; font-size: 16px; line-height: 1.65">\n%s\n%s'
        '</div>\n'
        '<!-- ============ end Advanced Sales Analysis %s listing ============ -->\n'
        '   </body>\n</html>\n'
        % (V['v'], V['v'], head_comment, WHITE, BODY, FONT, style, body, V['v'])
    )


def main(argv):
    keys = [a for a in argv[1:] if not a.startswith('-')] or list(VERSIONS)
    out_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for key in keys:
        if key not in VERSIONS:
            print('unknown version: %s (have %s)'
                  % (key, ', '.join(VERSIONS)), file=sys.stderr)
            return 2
        html = build(key)
        non_ascii = sorted({c for c in html if ord(c) > 127})
        if non_ascii:
            print('non-ASCII characters in the %s output: %r'
                  % (key, non_ascii), file=sys.stderr)
            return 2
        dest = os.path.join(out_root, 'advanced_sales_analysis_%s' % key,
                            'static', 'description', 'index.html')
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'w', encoding='ascii', newline='\n') as fh:
            fh.write(html)
        print('wrote %s  (%d bytes)' % (dest, len(html)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
