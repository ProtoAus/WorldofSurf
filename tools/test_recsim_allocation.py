"""Allocation and equivalence controls for the bounded similarity reader."""
import hashlib
from pathlib import Path
import random
import tempfile
import tracemalloc
from types import SimpleNamespace
import unittest
from unittest import mock

from test_recsim_parsing import rs, recording


def previous_alignment(a, b, *, max_shift=None, min_len=0):
    """Reference: the exhaustive per-offset alignment and prefix calculation."""
    sa, sb = list(zip(a.moves, a.btns)), list(zip(b.moves, b.btns))
    if not sa or not sb or min(len(sa), len(sb)) < min_len:
        return (0, 0, 0, 0, 0.0)
    width = 4 if max_shift is None else max_shift
    best = (b.mt[0] - a.mt[0], 0, 0, 0, 0.0)
    for d in range(-width, width + 1):
        overlap = [x == y for x, y in zip(sa[max(0, -d):], sb[max(0, d):])]
        matched, compared = sum(overlap), len(overlap)
        if matched > best[1] or (not best[2] and compared):
            prefix = next((i for i, eq in enumerate(overlap) if not eq), compared)
            best = (d, matched, compared, prefix, prefix / max(len(sa), len(sb)))
    return best


class Allocation(unittest.TestCase):
    def test_bounded_capture_decodes_without_full_unicode_duplicate(self):
        # Enough size to discriminate retained memory; each line remains short and ordinary.
        left = recording().replace('begin\n', 'begin\r\n', 1).encode('ascii')
        rows = ('# ' + 'short annotation ' * 15 + '\U0001f30a\r\n').encode('utf-8') * 12000
        data = left.replace(b'begin\r\n', b'begin\r\n' + rows, 1)
        with tempfile.TemporaryDirectory(prefix='recsim-allocation-') as directory:
            p = Path(directory) / 'sample.rec'
            p.write_bytes(data)
            with mock.patch.object(rs.locale, 'getpreferredencoding', return_value='utf-8'):
                tracemalloc.start()
                try:
                    got = rs.parse_rec(str(p), strict=True, max_bytes=len(data), max_moves=80)
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
        self.assertEqual(got.source, {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        self.assertEqual((got.map, len(got.moves)), ('synthetic', 80))
        print(f'bounded decode: {len(data):,} input bytes, {peak:,} traced peak bytes', flush=True)
        self.assertLess(peak, 3 * len(data), 'retained a full Unicode copy of an already-captured buffer')

    def test_alignment_materializes_only_two_streams(self):
        def run(moves):
            return SimpleNamespace(moves=[(i, 0, 0) for i in moves], btns=[1] * len(moves),
                                   mt=list(range(len(moves))), yaw=[0] * len(moves))

        a, b = run(list(range(100))), run([454, 123] + list(range(97)) + [211])
        self.assertEqual(previous_alignment(a, b), (2, 97, 98, 97, 0.97))
        with mock.patch.object(rs, 'stream', wraps=rs.stream) as stream:
            self.assertEqual(rs.best_offset(a, b), (2, 97, 98, 97, 0.97))
            print(f'alignment stream materializations: {stream.call_count}', flush=True)
            self.assertEqual(stream.call_count, 2)
        self.assertEqual(rs.prefix_len(a, b, 2), 97)

    def test_alignment_matches_reference_for_short_and_offset_pairs(self):
        rng = random.Random(420)

        def run(length):
            start = rng.randint(-50, 50)
            return SimpleNamespace(moves=[(rng.randrange(3), 0, 0) for _ in range(length)],
                                   btns=[rng.randrange(2) for _ in range(length)],
                                   yaw=[0] * length, mt=list(range(start, start + length)))

        for _ in range(250):
            a, b = run(rng.randrange(25)), run(rng.randrange(25))
            args = {'max_shift': rng.choice([None, 0, 1, 20]), 'min_len': rng.randrange(11)}
            self.assertEqual(rs.best_offset(a, b, **args), previous_alignment(a, b, **args))


if __name__ == '__main__':
    unittest.main()
