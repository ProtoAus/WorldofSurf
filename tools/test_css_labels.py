"""P1828: display names change without renaming imported formats or commands."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
# QC also has single-quoted vectors/chars; their quotes must not start strings.
TOKENS = re.compile(r'''//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"''')


def strings(path):
    return [m[0][1:-1] for m in TOKENS.finditer(path.read_text()) if m[0].startswith('"')]


class CssLabels(unittest.TestCase):
    def test_runtime_display_labels(self):
        credits = {
            'owner KSF',
        }
        seen = set()
        for directory in ('client', 'menu', 'server', 'shared'):
            for path in (ROOT / 'src' / directory).glob('*.qc'):
                for text in strings(path):
                    if 'KSF' in text:
                        self.assertIn(text, credits, f'{path.relative_to(ROOT)}: {text}')
                        seen.add(text)
        self.assertEqual(seen, credits)
        for file, label in {
            'client/cl_groups.qc': 'CS:S',
            'client/cl_profile.qc': 'CS:S',
            'client/cl_scores.qc': '[CS:S] ',
            'client/cl_maptier.qc': 'CS:S tier %g',
            'menu/m_board.qc': 'CS:S (ksf.surf): times and available replays',
            'menu/m_tournament.qc': 'Momentum %s  |  CS:S %s',
        }.items():
            self.assertIn(label, strings(ROOT / 'src' / file), file)

    def test_replay_source_display_does_not_expose_import_token(self):
        source = (ROOT / 'src/client/cl_watch.qc').read_text()
        self.assertIn('if (!strcmp(rec_wt_source, "ksf")) return "CS:S";', source)
        self.assertIn('strcat(Watch_SourceName(), " import (not verified)")', source)
        self.assertNotIn('strcat(rec_wt_source, " import (not verified)")', source)
        self.assertIn('Watch_SourceName(), rec_wt_momdemo,', source)
        self.assertIn('track, leg, Watch_SourceName()', source)

    def test_import_identifiers_and_attribution_preserved(self):
        expected = {
            'client/cl_ksf.qc': ['foreign ksf original-binary css66', 'owner KSF',
                                 'ksfdemo %i %i %i %s', 'ksfground %g', 'ksfmoves %g', 'ksfbuttons %i %i'],
            'client/cl_jargon.qc': ['ksftime', 'ksf_', 'cfg/ksfreplays/*.rec', 'ksf'],
            'client/cl_profile.qc': ['ksf_sync', 'ksf'],
            'client/cl_zoneedit.qc': ['ksfTier', r'\"ksfTier\":%g,'],
            'client/cl_watch.qc': ['ksf', r'replay: ksf <binary.rec> <map> <bonus: 0=main> <FW|SW|HSW|BW>\n'],
            'server/sv_tasoptimize.qc': ['ksfbuttons', 'cfg/ksfreplays/'],
        }
        for file, labels in expected.items():
            actual = strings(ROOT / 'src' / file)
            for label in labels:
                self.assertIn(label, actual, file)


if __name__ == '__main__':
    unittest.main()
