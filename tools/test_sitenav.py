#!/usr/bin/env python3
"""P1820: tools/sitenav.py keeps one tab list on every page.  python3 tools/test_sitenav.py"""
import importlib.util
import os
import re
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load():
    spec = importlib.util.spec_from_file_location('sitenav', os.path.join(HERE, 'sitenav.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SiteNav(unittest.TestCase):
    def setUp(self):
        self.nav = load()
        self.tmp = tempfile.mkdtemp(prefix='sitenav-')
        self.addCleanup(shutil.rmtree, self.tmp)

    def copy_tree(self):
        for rel in self.nav.SCAN:
            src = os.path.join(ROOT, rel)
            dst = os.path.join(self.tmp, rel)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)

    def test_repo_is_in_sync(self):
        self.assertEqual(self.nav.run(ROOT, check=True), 0)

    def test_every_public_header_lists_every_tab(self):
        labels = [label for _k, label, _p in self.nav.PUBLIC]
        seen = 0
        for rel in self.nav.files(ROOT):
            with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
                text = fh.read()
            for m in self.nav.HTML_BLOCK.finditer(text):
                if m.group('kind') != 'header':
                    continue
                seen += 1
                got = re.findall(r'<a[^>]*>([^<]+)</a>', m.group('body').split('<div class="links')[1].split('</div>')[0])
                self.assertEqual(got, labels, rel)
                self.assertIn('Log in</a>', m.group('body'), rel)
        self.assertGreaterEqual(seen, 6)      # index, anticheat, zoning, get, board, watch

    def test_a_new_tab_reaches_every_page(self):
        # The mutation the tool exists for: one edit to PUBLIC, and --check names every page that lacks it.
        self.copy_tree()
        self.nav.PUBLIC = self.nav.PUBLIC + (('maps', 'Maps', 'maps.html'),)
        self.assertEqual(self.nav.run(self.tmp, check=True), 1)
        self.assertEqual(self.nav.run(self.tmp, check=False), 0)
        self.assertEqual(self.nav.run(self.tmp, check=True), 0)
        for rel in ('src/release/site/zoning.html', 'surfd/web/board.html', 'src/release/page.template.html'):
            with open(os.path.join(self.tmp, rel), encoding='utf-8') as fh:
                self.assertIn('>Maps</a>', fh.read(), rel)

    def test_a_page_with_a_menu_and_no_block_fails(self):
        self.copy_tree()
        with open(os.path.join(self.tmp, 'src/release/site/new.html'), 'w') as fh:
            fh.write('<html><body><header class="nav"><nav class="nav-in"><a href="./">Overview</a></nav></header>')
        self.assertEqual(self.nav.run(self.tmp, check=True), 1)

    def test_a_misindented_closer_eats_nothing(self):
        # Review 1: the closer had to repeat the opener's indent, so a match ran on to the next block's closer and the
        # rewrite deleted everything between (here <main> and the footer's opener).
        self.copy_tree()
        path = os.path.join(self.tmp, 'src/release/site/zoning.html')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        # The header's opener indented two spaces, its closer left at column 0: the old pattern's next "  <!-- /sitenav -->"
        # was the tail of the footer's (four-space) closer.
        text = text.replace('<!-- sitenav:header page=zoning base=./ -->', '  <!-- sitenav:header page=zoning base=./ -->')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        self.nav.run(self.tmp, check=False)
        with open(path, encoding='utf-8') as fh:
            after = fh.read()
        self.assertIn('<main class="compact zoning">', after)
        self.assertIn('<!-- sitenav:footer base=./ -->', after)
        self.assertEqual(after.count('<header class="nav">'), 1)

    def test_an_unpaired_marker_is_refused(self):
        self.copy_tree()
        path = os.path.join(self.tmp, 'src/release/site/anticheat.html')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text.replace('<!-- /sitenav -->', '', 1))
        self.assertEqual(self.nav.run(self.tmp, check=False), 1)
        with open(path, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), text.replace('<!-- /sitenav -->', '', 1))      # untouched

    def test_prose_about_the_tool_is_not_a_marker(self):
        self.copy_tree()
        path = os.path.join(self.tmp, 'src/release/site/anticheat.html')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text.replace('<body>', '<body>\n<!-- sitenav.py writes the header below -->', 1))
        self.assertEqual(self.nav.run(self.tmp, check=True), 0)

    def test_board_keeps_its_hash_hooks(self):
        out = self.nav.header({'page': 'board', 'base': '../'}, '')
        self.assertIn('<a data-tab="board" href="#">Leaderboard</a>', out)
        self.assertIn('<a data-tab="people" href="#who=">Players</a>', out)
        self.assertNotIn('aria-current', out)          # board.js navTab() owns it
        self.assertIn('href="../zoning.html"', out)

    def test_hrefs(self):
        h = self.nav.href
        self.assertEqual(h('./', './'), './')
        self.assertEqual(h('./', 'board/'), 'board/')
        self.assertEqual(h('./', './#download'), './#download')
        self.assertEqual(h('../', 'zoning.html'), '../zoning.html')
        self.assertEqual(h(self.nav.SITE, './#download'), self.nav.SITE + '#download')
        self.assertEqual(h('../', 'https://play.proto.bar/tasup/'), 'https://play.proto.bar/tasup/')

    def test_python_block_is_valid_python(self):
        src = self.nav.python({'page': 'tas', 'base': self.nav.SITE}, '')
        scope = {}
        exec(src, scope)
        labels = [l for l, _u in scope['SITE_NAV']]
        self.assertEqual(labels, [label for _k, label, _p in self.nav.PUBLIC])
        self.assertIsNone(dict(scope['SITE_NAV'])['TAS uploads'])
        self.assertEqual(scope['SITE_PILLS'][1], ('Log in', self.nav.LOGIN))

    def test_admin_menu(self):
        out = self.nav.admin({'page': 'runs'}, '  ')
        self.assertIn('<a href="/admin/runs" aria-current="page">Runs</a>', out)
        self.assertEqual(out.count('aria-current'), 1)
        self.assertIn('{% include "_admin_brand.html" %}', out)
        self.assertNotIn('<nav', self.nav.admin({'page': 'fleet', 'nav': '0'}, ''))
        self.assertNotIn('brand', self.nav.admin({'page': 'fleet', 'brand': '0'}, ''))
        # reportd_reports.html's script writes the unseen count into #navunseen; without it the page throws.
        self.assertIn('Reports <span class="pill info" id="navunseen" hidden></span></a>', self.nav.admin({'page': 'reports'}, ''))
        self.assertNotIn('navunseen', out)


if __name__ == '__main__':
    unittest.main()
