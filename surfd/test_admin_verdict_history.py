#!/usr/bin/env python3
"""Truthful bounded historical attempts: actual API/SQL acquisition and DOM."""
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

from test_admin_metric_bounds import ObservationFixture


class VerdictHistory(ObservationFixture):
    def populate(self, n):
        self.c.execute('DELETE FROM verdicts')
        self.c.execute('UPDATE replays SET submitted=100 WHERE id=?', (self.rid,))
        self.c.executemany("INSERT INTO verdicts(replay_id,verdict,reason,ticks,engine,progs,at)"
                           " VALUES(?,'PASS','synthetic history',100,'e','p',?)",
                           ((self.rid, 2000000000 if i == 0 else 1) for i in range(n)))
        self.c.commit()

    def board(self):
        result = self.m.app.test_client().get('/api/board?map=bhop_eazy').get_json()
        result.pop('t', None)
        return result

    def test_actual_api_boundaries_acquisition_order_and_public_state(self):
        connect = sqlite3.connect
        acquired = []

        class Cursor(sqlite3.Cursor):
            def fetchall(self):
                rows = super().fetchall()
                if self.history:
                    acquired.append(len(rows))
                return rows

        class Connection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                cur = self.cursor(factory=Cursor)
                cur.history = 'FROM verdicts WHERE replay_id' in sql and 'counts_metrics' in sql
                return cur.execute(sql, parameters)

        for n in (0, 199, 200, 201, 400):
            with self.subTest(n=n):
                self.populate(n)
                before = tuple(self.c.iterdump())
                board = self.board()
                acquired.clear()
                with mock.patch.object(sqlite3, 'connect', side_effect=lambda *a, **kw: connect(*a, **dict(kw, factory=Connection))):
                    value = self.detail()
                self.assertEqual(acquired, [min(n, 201)])
                self.assertEqual(value.get('verdict_history'), {'limit': 200, 'more': n > 200})
                ids = [r['id'] for r in value['verdicts']]
                expected = [r[0] for r in self.c.execute('SELECT id FROM verdicts ORDER BY id DESC LIMIT 200')]
                self.assertEqual(ids, expected)
                self.assertEqual(value['public'], 'verified' if n else 'plain')
                if n > 200:
                    self.assertFalse(any(r['current'] for r in value['verdicts']))
                self.assertEqual(tuple(self.c.iterdump()), before)
                self.assertEqual(self.board(), board)
        self.assertEqual(self.m.app.test_client().get(self.route).status_code, 401)

    def test_current_attempt_outside_history_keeps_its_explanation(self):
        self.populate(400)
        value = self.detail()
        self.assertFalse(any(row['current'] for row in value['verdicts']))
        self.assertEqual(value['public'], 'verified')
        self.assertEqual(value.get('verdict_explanation', {}).get('verdict'), 'PASS')
        self.assertEqual(value['verdict_explanation']['reason'], 'synthetic history')
        self.assertIn('synthetic history', self.explanation_dom(value))

    def test_current_non_error_takes_precedence_and_error_only_still_explains(self):
        self.populate(201)
        self.c.execute("UPDATE verdicts SET at=200, verdict='ERROR', reason='synthetic IO failure' "
                       "WHERE id=(SELECT max(id) FROM verdicts)")
        self.c.commit()
        value = self.detail()
        self.assertEqual(value['verdicts'][0]['verdict'], 'ERROR')
        self.assertEqual(value.get('verdict_explanation', {}).get('verdict'), 'PASS')
        self.c.execute("DELETE FROM verdicts WHERE at=2000000000")
        self.c.commit()
        value = self.detail()
        self.assertEqual(value['verdict_explanation']['verdict'], 'ERROR')
        self.assertIn('synthetic IO failure', self.explanation_dom(value))
        self.c.execute("UPDATE verdicts SET at=1")
        self.c.commit()
        value = self.detail()
        self.assertIsNone(value['verdict_explanation'])
        self.assertIn('Not checked yet', self.explanation_dom(value))

    def explanation_dom(self, value):
        if not shutil.which('node'):
            self.skipTest('Node absent')
        text = Path(self.a.__file__).with_name('templates').joinpath('admin_run.html').read_text(encoding='utf-8')
        start = text.index('function renderExplain(')
        fragment = text[start:text.index('  const st = j.standing', start)] + '}\n'
        js = r'''
class E {
  constructor(text){this.text=String(text??'');this.children=[];this.dataset={};this.classList={add(){}};}
  replaceChildren(...children){this.children=children;}
  append(...children){this.children.push(...children);}
  set innerHTML(value){throw Error('HTML sink');}
  flatten(){return this.text+this.children.map(p=>p instanceof E?p.flatten():String(p)).join('');}
}
const box=new E(), el=(t,c,s)=>new E(s), pill=(s,c)=>new E(s), VERDICT_CLS={},PUBLIC_CLS={},PUBLIC_TIP={};
const document={getElementById:(id)=>id==='explain'?box:new E()};
''' + fragment + r'''
renderRun(JSON.parse(process.argv[2]));
console.log(box.flatten());
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'explain.js'
            path.write_text(js, encoding='utf-8')
            result = subprocess.run(['node', str(path), json.dumps(value)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

    def dom(self, verdicts, history):
        if not shutil.which('node'):
            self.skipTest('Node absent; actual DOM tested on Windows')
        text = Path(self.a.__file__).with_name('templates').joinpath('admin_run.html').read_text(encoding='utf-8')
        start = text.find('function renderVerdictSummary(')
        if start >= 0:
            block = text[start:text.index('function renderRun(', start)]
        else:
            # Execute the predecessor's actual inline summary, not an absent-helper red.
            start = text.index('  const cur = j.verdicts.filter(')
            block = ('function renderVerdictSummary(verdicts, history) {const j={verdicts};' +
                     text[start:text.index('  const RCPT_CLS', start)] + '}')
        js = r'''
class E {constructor(text){this.text=String(text??'');} set innerHTML(v){throw Error('HTML sink');}}
const el=(t,c,s)=>new E(s),pill=(s,c)=>new E(s),VERDICT_CLS={};
let result;
const summarise=(id,flag,...parts)=>{result={id,flag,text:parts.map(p=>p instanceof E?p.text:String(p)).join(' ')};};
''' + block + r'''
renderVerdictSummary(JSON.parse(process.argv[2]),JSON.parse(process.argv[3]));
console.log(JSON.stringify(result));
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'render.js'
            path.write_text(js, encoding='utf-8')
            projected = [{k: v[k] for k in ('current', 'verdict')} for v in verdicts]
            p = subprocess.run(['node', str(path), json.dumps(projected), json.dumps(history)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)

    def test_actual_dom_never_claims_omitted_attempts_are_all_stale(self):
        self.populate(201)
        value = self.detail()
        rendered = self.dom(value['verdicts'], value.get('verdict_history', {'limit': 200, 'more': True}))
        self.assertIn('shown', rendered['text'])
        self.assertIn('older attempts omitted', rendered['text'])
        self.assertNotIn('all 200', rendered['text'])
        self.assertTrue(rendered['flag'])

    def test_actual_dom_complete_empty_and_mixed_controls(self):
        self.assertIn('not verified yet', self.dom([], {'limit': 200, 'more': False})['text'])
        stale = [{'current': False, 'verdict': 'PASS'}]
        self.assertIn('all 1 predate', self.dom(stale, {'limit': 200, 'more': False})['text'])
        mixed = [{'current': True, 'verdict': 'PASS'}, *stale]
        result = self.dom(mixed, {'limit': 200, 'more': True})
        self.assertIn('1 current, 1 stale shown', result['text'])
        self.assertIn('older attempts omitted', result['text'])
        self.assertFalse(result['flag'])


if __name__ == '__main__':
    unittest.main()
