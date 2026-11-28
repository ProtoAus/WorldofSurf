"""P1859 review round 2: a notable re-measure through the cron (hard_process) path is a valid worker result.

The worker's answer is refused when notable > stored; counting replacements as notable but not stored made every
notable re-measure 'similarity worker returned an invalid result'.  Runs the real recsim in a subprocess."""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCRIPT = textwrap.dedent('''
    import importlib, os, sys
    from pathlib import Path
    here, home = Path(sys.argv[1]), Path(sys.argv[2])
    sys.path.insert(0, str(here))
    (home / "surfd.env").write_text("SURFD_KEY=testkey\\n")
    runs = home / "runs"; runs.mkdir()
    os.environ.update(SURFD_HOME=str(home), SURFD_ENV=str(home / "surfd.env"), SURFD_RUNS=str(runs),
                      SURFD_GAME=str(home), SURFD_DB=str(home / "x.db"), SURFD_TOOLS=str(here.parent / "tools"))
    for k in ("SURFD_EVIDENCE", "SURFD_KEEP"):
        os.environ.pop(k, None)
    app = importlib.import_module("surfd"); sweep = importlib.import_module("sweep")
    app.DB_PATH = str(home / "x.db"); app.migrate(); conn = app.connect(); sweep.ensure_schema(conn)
    sweep.TOOLS = str(here.parent / "tools")
    d = runs / "surf_control/main"; d.mkdir(parents=True)
    for index, who in enumerate(("control-abcdef12", "control-12345678"), 1):
        leaf = "%07d_pb.rec" % index
        body = ["FTESURF-REC 9", "map surf_control", "track 0", "leg 0", "tickrate 0.015", "who " + who, "begin"]
        body += ["in %d %d 0 %d %d 0 0 0 0 0 1" % (i, i, (i * 7) % 451, (i * 3) % 451) for i in range(400)]
        body += ["end 400 0 0 0 0 0 0 0 0 0 0 0"]
        (d / leaf).write_text("\\n".join(body) + "\\n")
        conn.execute("INSERT INTO replays (map,map_dir,track,leg,leaf,tier,style,player,name,ticks,tickrate,millis,"
                     "flags,node,submitted,kind) VALUES ('surf_control','surf_control',0,0,?,'ranked','normal',?,"
                     "'control',400,66.6667,6000,0,'1',1,'run')", (leaf, who))
    conn.commit()
    import simcheck; simcheck.ensure_schema(conn); conn.commit()
    conn.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,reason,skip_code,at,reader) VALUES"
                 "(1,2,'surf_control',0,0,'skip','old reader: unmodelled','unmodelled',0,1)")
    conn.commit()
    print("STEP", repr(sweep.similarity_step(conn, hard_process=True)))
    print("ROW", repr(tuple(conn.execute("SELECT verdict, round(match, 3), reader FROM sims").fetchone())))
''')


class RemeasureProcess(unittest.TestCase):
    def test_a_notable_remeasure_is_a_valid_worker_result(self):
        with tempfile.TemporaryDirectory() as home:
            out = subprocess.run([sys.executable, '-B', '-c', SCRIPT, str(HERE), home], capture_output=True,
                                 text=True, timeout=300, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        lines = dict(l.split(' ', 1) for l in out.stdout.splitlines() if l.startswith(('STEP ', 'ROW ')))
        self.assertIn('STEP', lines, out.stdout[-500:] + out.stderr[-1500:])
        step = eval(lines['STEP'])
        self.assertEqual(eval(lines['ROW']), ('compared', 1.0, 2), 'the stale skip was re-measured as a notable pair')
        self.assertNotIn('invalid result', step[2])
        self.assertEqual(step[:2], (1, 1), step)
        self.assertIn('sims re-measured 1 (0 unjudgeable)', step[2])


if __name__ == '__main__':
    unittest.main()
