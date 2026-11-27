#!/usr/bin/env python3
"""One tab list for every page of the site and the admin.

Lex, 25 Nov 2026: "sometimes a bot will add a tab and it won't appear on all the pages". Every header, footer link
row and admin menu is a generated block between markers:

    <!-- sitenav:header page=zoning base=./ -->  ...  <!-- /sitenav -->
    <!-- sitenav:footer base=./ -->              ...  <!-- /sitenav -->
    <!-- sitenav:admin page=runs -->             ...  <!-- /sitenav -->
    # sitenav:python base=https://proto.bar/worldofsurf/ page=tas  ...  # /sitenav   (tasupd.py's SITE_NAV tuple)

    python3 tools/sitenav.py           rewrite every block from the lists below
    python3 tools/sitenav.py --check   exit 1 when a page is out of date, or a page with a menu has no block

To add a tab: edit PUBLIC or ADMIN, run the script, commit every file it names. Each page still ships with its own
service (site release, board publish, tasupd install, surfd generation), so a tab reaches the live pages when each
of those next deploys; this keeps the sources from drifting.
"""
import argparse
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://proto.bar/worldofsurf/'
LOGIN = 'https://play.proto.bar/admin/'

# (key, label, href from the site root -- or absolute)
PUBLIC = (
    ('home', 'Overview', './'),
    ('board', 'Leaderboard', 'board/'),
    ('people', 'Players', 'board/#who='),
    ('zoning', 'Zoning', 'zoning.html'),
    ('anticheat', 'Anti-Cheat', 'anticheat.html'),
    ('tas', 'TAS uploads', 'https://play.proto.bar/tasup/'),
)
DOWNLOAD = ('Download', './#download')
FOOTER_EXTRA = (('Source', 'https://github.com/ProtoAus/WorldofSurf'),)
ADMIN = (
    ('fleet', 'Fleet', '/admin/'),
    ('maps', 'Maps', '/admin/maps'),
    ('runs', 'Runs', '/admin/runs'),
    ('top10', 'Top 10', '/admin/top10'),
    ('accounts', 'Accounts', '/admin/accounts'),
    ('reports', 'Reports', '/admin/reports'),
)
# Markup a page's own script fills in (reportd_reports.html counts unseen reports into #navunseen).
ADMIN_EXTRA = {'reports': ' <span class="pill info" id="navunseen" hidden></span>'}
# The board switches views by hash: board.js navTab() lights these data-tab hooks, so the markup marks none.
BOARD_HOOKS = {'home': ('dl', '../'), 'board': ('board', '#'), 'people': ('people', '#who=')}

# Files that may carry blocks; every page in them with a site/admin menu must carry one (--check).
SCAN = ('src/release/page.template.html', 'src/release/site', 'surfd/web', 'surfd/templates', 'surfd/tasupd.py')
NO_MENU = {'surfd/templates/_admin_style.html'}

# The body may not cross another marker, and the closer's indent is free (the block is rewritten at the opener's):
# a mis-indented closer must not let a match run on and eat the page up to the next block's end.
HTML_BLOCK = re.compile(r'(?P<indent>[ \t]*)<!-- sitenav:(?P<kind>header|footer|admin)(?P<args>[^>]*?)-->\n'
                        r'(?P<body>(?:(?!<!-- /?sitenav).)*?)[ \t]*<!-- /sitenav -->', re.S)
PY_BLOCK = re.compile(r'(?P<indent>[ \t]*)# sitenav:(?P<kind>python)(?P<args>[^\n]*)\n'
                      r'(?P<body>(?:(?!# /?sitenav).)*?)[ \t]*# /sitenav', re.S)
MARKERS = re.compile(r'<!-- sitenav:|<!-- (/)sitenav -->|# sitenav:|# (/)sitenav[ \t]*$', re.M)
MENU = re.compile(r'<nav\b|SITE_NAV\s*=')


def esc(s):
    return html.escape(s, quote=True)


def href(base, path):
    if path.startswith(('https://', 'http://', '/')):
        return path
    rest = path[2:] if path.startswith('./') else path
    if base == './' and rest and not rest.startswith('#'):
        return rest                         # zoning.html, board/ -- as the pages always wrote them
    return base + rest


def parse_args(text):
    out = {}
    for tok in text.split():
        k, sep, v = tok.partition('=')
        if not sep or not k:
            raise ValueError('bad sitenav argument %r' % tok)
        out[k] = v
    return out


def header(a, indent):
    base, page = a.get('base', './'), a.get('page', '')
    board = page == 'board'
    links = []
    for key, label, path in PUBLIC:
        hook, url, cur = '', href(base, path), ''
        if board and key in BOARD_HOOKS:
            tab, url = BOARD_HOOKS[key]
            hook = ' data-tab="%s"' % tab
        if key == page and not board:
            cur = ' aria-current="page"'
        links.append('      <a%s href="%s"%s>%s</a>' % (hook, esc(url), cur, esc(label)))
    lines = ['<header class="nav">',
             '  <nav class="nav-in" aria-label="Site">',
             '    <a class="brand" href="%s" aria-label="World of Surf home"><span>World of</span><b>Surf</b></a>'
             % esc(base),
             '    <div class="links%s">' % (' tabs' if board else '')] + links + [
             '    </div>',
             '    <a class="pill" href="%s">%s</a>' % (esc(href(base, DOWNLOAD[1])), DOWNLOAD[0]),
             '    <a class="pill pill-quiet" href="%s">Log in</a>' % esc(LOGIN),
             '  </nav>',
             '</header>']
    return ''.join(indent + l + '\n' for l in lines)


def footer(a, indent):
    base = a.get('base', './')
    items = [(label, href(base, path)) for _key, label, path in PUBLIC]
    items += [(DOWNLOAD[0], href(base, DOWNLOAD[1]))] + list(FOOTER_EXTRA)
    body = ''.join('<a href="%s">%s</a>' % (esc(u), esc(l)) for l, u in items)
    return indent + '<div class="fnav">' + body + '</div>\n'


def admin(a, indent):
    # nav=0 / brand=0: one half alone (the fleet page shows its menu only when surfd has runs or bans).
    page = a.get('page', '')
    links = ''.join('<a href="%s"%s>%s%s</a>' % (url, ' aria-current="page"' if key == page else '', esc(label),
                                                 ADMIN_EXTRA.get(key, '') if key == page else '')
                    for key, label, url in ADMIN)
    brand = (indent + '<a class="brand" href="/admin/" aria-label="World of Surf admin">'
             '{% include "_admin_brand.html" %}<span class="tag">Admin</span></a>\n')
    if a.get('nav') == '0':
        return brand
    return ('' if a.get('brand') == '0' else brand) + (indent + '<nav class="nav" aria-label="Admin">' + links +
            '<a class="site-link" href="%s">Site &#8599;</a></nav>\n' % esc(SITE))


def python(a, indent):
    # tasupd.py: (label, url) pairs; None marks this service's own page.
    base, page = a.get('base', SITE), a.get('page', '')
    rows = ['SITE_NAV = (']
    for key, label, path in PUBLIC:
        rows.append('    (%r, %s),' % (label, 'None' if key == page else repr(href(base, path))))
    rows.append(')')
    rows.append('SITE_PILLS = ((%r, %r), (%r, %r))' % (DOWNLOAD[0], href(base, DOWNLOAD[1]), 'Log in', LOGIN))
    return ''.join(indent + r + '\n' for r in rows)


RENDER = {'header': header, 'footer': footer, 'admin': admin, 'python': python}


def regenerate(text):
    def one(m):
        body = RENDER[m.group('kind')](parse_args(m.group('args')), m.group('indent'))
        if m.group('kind') == 'python':
            return '%s# sitenav:python%s\n%s%s# /sitenav' % (m.group('indent'), m.group('args'), body, m.group('indent'))
        return '%s<!-- sitenav:%s%s-->\n%s%s<!-- /sitenav -->' % (
            m.group('indent'), m.group('kind'), m.group('args'), body, m.group('indent'))
    text = HTML_BLOCK.sub(one, text)
    return PY_BLOCK.sub(one, text)


def files(root):
    for rel in SCAN:
        path = os.path.join(root, rel)
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                if name.endswith('.html'):
                    yield os.path.join(rel, name)
        elif os.path.isfile(path):
            yield rel


def run(root, check):
    stale, unblocked, broken = [], [], []
    for rel in files(root):
        path = os.path.join(root, rel)
        with open(path, encoding='utf-8', newline='') as fh:
            text = fh.read()
        blocks = len(HTML_BLOCK.findall(text)) + len(PY_BLOCK.findall(text))
        marks = [bool(m.group(1) or m.group(2)) for m in MARKERS.finditer(text)]
        if len(marks) != 2 * blocks or marks != [False, True] * blocks:
            broken.append(rel)              # an unpaired or nested marker: never rewrite around it
            continue
        if not blocks:
            if rel not in NO_MENU and MENU.search(text):
                unblocked.append(rel)
            continue
        new = regenerate(text)
        if new != text:
            stale.append(rel)
            if not check:
                with open(path, 'w', encoding='utf-8', newline='') as fh:
                    fh.write(new)
    for rel in broken:
        print('BROKEN    %s has an unpaired or nested sitenav marker; fix it by hand (nothing written)' % rel)
    for rel in unblocked:
        print('NO BLOCK  %s has a menu but no sitenav block' % rel)
    for rel in stale:
        print(('STALE     ' if check else 'rewrote   ') + rel)
    return 1 if unblocked or broken or (check and stale) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='report, do not write; exit 1 when out of date')
    ap.add_argument('--root', default=ROOT)
    args = ap.parse_args(argv)
    return run(args.root, args.check)


if __name__ == '__main__':
    sys.exit(main())
