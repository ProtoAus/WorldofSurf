// Synthetic DOM/network controls for the public scripts; no browser/layout claim.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');
const baseIndex = process.argv.indexOf('--base');
const base = baseIndex >= 0 ? process.argv[baseIndex + 1] : null;
const path = require('node:path');
const root = path.resolve(__dirname, '..');
class Element {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.events = {}; this.attrs = {};
    this.value = ''; this.style = {}; this.hidden = false; this.checked = false;
    this.classList = { add() {} };
  }
  set textContent(s) { this.text = String(s); this.children = []; }
  get textContent() { return (this.text || '') + this.children.map(x => x.textContent).join(''); }
  appendChild(e) {
    if (e.tagName === 'fragment') { e.children.forEach(x => this.appendChild(x)); return e; }
    this.children.push(e); e.parentNode = this; return e;
  }
  remove() { this.parentNode.children = this.parentNode.children.filter(x => x !== this); }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k]; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(k, f) { this.events[k] = f; }
  querySelectorAll() { return []; }
  querySelector(tag) {
    for (const child of this.children) {
      if (child.tagName === tag) return child;
      const match = child.querySelector(tag);
      if (match) return match;
    }
    return null;
  }
  focus() { this.focused = true; }
  get firstChild() { return this.children[0]; }
}
function harness(file) {
  const ids = {}, requests = [], timers = new Map(), events = {}, winEvents = {};
  const chips = ['active', 'az', 'runs', 'times', 'demos', 'tier'].map(k => { const e = new Element('button'); e.setAttribute('data-sort', k); return e; });
  let tid = 0;
  const document = {
    head: new Element('head'), hidden: false,
    getElementById(id) { return ids[id] || (ids[id] = new Element()); },
    createElement: t => new Element(t), createDocumentFragment: () => new Element('fragment'),
    createTextNode: t => { const e = new Element(); e.textContent = t; return e; },
    querySelectorAll: s => s === '.chip[data-sort]' ? chips : [], addEventListener: (k, f) => { events[k] = f; }
  };
  const context = {
    wosDownload: { NAME: /^[a-z0-9_]+$/i, button(kind, map) { const e = new Element('a'); e.href = kind + '/' + map; return e; } },
    document, location: { hash: '' },
    history: { replaceState(_state, _title, hash) { context.location.hash = hash; } }, console, Date,
    Image: function () {},
    setTimeout(f, ms) { timers.set(++tid, { f, ms }); return tid; },
    clearTimeout(id) { timers.delete(id); },
    fetch(url) {
      return new Promise((resolve, reject) => requests.push({ url, resolve: doc => resolve({ ok: true, json: () => Promise.resolve(doc) }), reject }));
    },
    addEventListener: (k, f) => { winEvents[k] = f; }
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(base ? execFileSync('git', ['show', base + ':' + file], { cwd: root, encoding: 'utf8' }) : fs.readFileSync(path.join(root, file), 'utf8'), context);
  return { ids, requests, document, events, winEvents, context, chips,
    timer(ms) { const e = [...timers].find(([, t]) => t.ms === ms); assert.ok(e, 'timer ' + ms); timers.delete(e[0]); e[1].f(); } };
}
const tick = async () => { for (let n = 0; n < 12; n++) await Promise.resolve(); };
async function board() {
  const h = harness('surfd/web/board.js');
  h.events.DOMContentLoaded();
  assert.equal(h.document.head.children.length, 0, 'no viewer on list route');
  const maps = Array.from({ length: 2500 }, (_, i) => ({ map: 'surf_' + String(i).padStart(4, '0'), runs: i % 2, imp: 0, last: i, mt: i % 2 + 1, have: 1 }));
  maps.push({ map: 'surf_archive', have: 0, runs: 0, imp: 56, reps: 1 });
  h.requests[0].resolve({ maps, tiers: true }); await tick();
  assert.equal(h.ids.maps.children.length, 100);
  assert.match(h.ids.summary.textContent, /2500 maps · 1250 with WOS times/);
  assert.ok(h.chips[3].hidden, 'mixing record counts is not a default sort');
  h.ids.q.value = 'surf_archive'; h.ids.q.events.input();
  assert.equal(h.ids.maps.children.length, 0);
  h.ids.archive.checked = true; h.ids.archive.events.change();
  assert.equal(h.ids.maps.children.length, 1, 'archive toggle recovers imported-only maps');
  assert.match(h.ids.maps.children[0].textContent, /56 imported/);
  h.chips[3].events.click();
  h.ids.archive.checked = false; h.ids.archive.events.change();
  assert.equal(h.chips[0].getAttribute('aria-pressed'), 'true', 'reset archive sort');
  h.ids.q.value = ''; h.ids.q.events.input();
  const firstMapNode = h.ids.maps.children[0];
  h.ids.mapsmore.events.click();
  assert.equal(h.ids.maps.children.length, 200);
  assert.equal(h.ids.maps.children[0], firstMapNode, 'load-more appends without rebuilding existing rows');
  assert.equal(h.ids.maps.children[100].children[0].focused, true, 'expansion focuses first new map');
  h.ids.q.value = 'surf_0000'; h.ids.q.events.input();
  assert.equal(h.ids.maps.children.length, 1, 'search beyond initial active page');
  assert.equal(h.ids.maps.children[0].children[0].href, '#m=surf_0000');
  assert.equal(h.ids.mapsmore.hidden, true);
  h.ids.q.value = ''; h.ids.q.events.input();
  assert.equal(h.ids.maps.children.length, 100, 'search reset restores cap');
  h.chips[1].events.click();
  assert.equal(h.ids.maps.children[0].children[0].href, '#m=surf_0000', 'sort covers entire catalogue');
  h.ids.mapsmore.events.click();
  h.ids.tiers.children[2].events.click();
  assert.equal(h.ids.maps.children.length, 100, 'tier filter resets cap');
  assert.match(h.ids.summary.textContent, /1250 matching/);
  assert.equal(h.ids.maps.children[0].children[0].href, '#m=surf_0001');
  h.ids.tiers.children[2].events.click();
  assert.match(h.ids.summary.textContent, /2500 maps/);
  const route = hash => { h.context.location.hash = hash; h.winEvents.hashchange(); };
  route('#r=one'); route('#r=two');
  assert.equal(h.document.head.children.length, 1, 'viewer singleflight');
  route('');
  h.document.head.children[0].onerror(); await tick();
  assert.equal(h.ids.err.hidden, true, 'stale script failure does not paint list error');
  route('#r=three');
  assert.equal(h.document.head.children.length, 1, 'failed script can retry');
  h.document.head.children[0].onerror(); await tick();
  assert.equal(h.ids.runretry.hidden, false);
  assert.match(h.ids.err.textContent, /retry/);
  h.ids.runretry.events.click();
  assert.equal(h.document.head.children.length, 1, 'retry button loads new external script');
  assert.equal(h.document.head.children[0].src, 'runview.js');
  h.context.FSRun = { View: function () { throw Error('stale render'); } };
  route(''); h.document.head.children[0].onload();
  h.requests.filter(r => r.url.startsWith('api/run/')).forEach(r => r.resolve({})); await tick();
  assert.equal(h.ids.err.hidden, true, 'stale success never instantiates viewer');
  assert.equal(h.ids.maps.children.length, 100, 'back route preserves map cap');
  let views = 0, destroyed = 0;
  const pauses = [];
  h.context.FSRun = { View: function (_canvas, _body, opts) {
    views++; pauses.push(opts.onpause);
    this.destroy = () => { destroyed++; opts.onpause(0.25); };
  } };
  route('#r=four');
  h.requests[h.requests.length - 1].resolve({ tr: 'ranked', name: 'Runner', disp: 'surf_test', map: 'surf_test', ms: 1234,
    track: 0, leg: 0, style: 'clean', when: 1, stats: { max_speed: 1, avg_speed: 1, duration: 1 }, head: {}, rid: 'four' });
  await tick();
  assert.equal(views, 1, 'loaded viewer renders current run');
  assert.match(h.ids.runtitle.textContent, /surf_test/);
  pauses[0](0.5);
  assert.equal(h.context.location.hash, '#r=four&at=0.50', 'current pause publishes timestamp');
  route('#r=five');
  assert.equal(h.context.location.hash, '#r=five', 'disposal cannot publish prior run hash');
  h.requests[h.requests.length - 1].reject(Error('synthetic failure')); await tick();
  h.ids.runretry.events.click();
  assert.equal(h.requests[h.requests.length - 1].url, 'api/run/five', 'retry targets failed destination, not disposed run');
  route('');
  assert.equal(destroyed, 1, 'replacement destroys old viewer once');
  pauses[0](1);
  assert.equal(h.context.location.hash, '', 'obsolete pause cannot hijack another route');
  console.log('PASS board: cap/search/focus/reset/back, lazy retry and callback-faithful stale navigation controls');
}
async function boardSources() {
  const h = harness('surfd/web/board.js');
  const route = hash => { h.context.location.hash = hash; h.winEvents.hashchange(); };
  const reply = async (tier, name, style = 'clean', track = 0, leg = 0) => {
    const req = h.requests.at(-1);
    const q = new URLSearchParams(req.url.split('?')[1]);
    assert.equal(q.get('tier'), tier);
    assert.equal(q.get('style'), style);
    assert.equal(Number(q.get('track')), track);
    assert.equal(Number(q.get('leg')), leg);
    const rows = name ? [{ r: 1, who: 'player', name, when: 1, ms: 3000, tr: tier }] : [];
    req.resolve({ tier, style, track, leg, map: 'surf_fixture', disp: 'surf_fixture', have: 1,
      n: rows.length, rows, counts: { ranked: 1, ksf: 2, momentum: 3 },
      ksf_topup: { eligible: true }, mom_topup: { eligible: true } });
    await tick();
  };
  h.context.location.hash = '#m=surf_fixture'; h.events.DOMContentLoaded();
  assert.match(h.requests.at(-1).url, /track=0&leg=0&style=clean&tier=ranked$/);
  await reply('ranked', 'Native runner');
  assert.match(h.ids.rows.textContent, /Native runner/);
  assert.equal(h.ids.ksftopup.children.length, 0, 'no import controls on WOS');
  assert.deepEqual(h.ids.srcs.children.map(b => b.textContent), ['WOS1', 'CS:S (KSF)2', 'Momentum Mod3']);
  assert.equal(h.ids.srcs.children[0].getAttribute('aria-pressed'), 'true');
  h.ids.srcs.children[1].events.click(); h.winEvents.hashchange();
  await reply('ksf', 'Source runner');
  assert.equal(h.ids.srcs.children[1].getAttribute('aria-pressed'), 'true');
  assert.match(h.ids.rows.textContent, /Source runner/);
  assert.doesNotMatch(h.ids.rows.textContent, /Native runner/);
  assert.match(h.context.location.hash, /tier=ksf$/);
  assert.match(h.ids.ksftopup.textContent, /Fetch/);
  h.ids.srcs.children[2].events.click(); h.winEvents.hashchange();
  await reply('momentum', 'Momentum runner');
  assert.match(h.ids.rows.textContent, /Momentum runner/);
  route('#m=surf_fixture&t=1&l=2&s=sw');
  await reply('ksf', 'Sideways runner', 'sw', 1, 2);
  assert.match(h.context.location.hash, /t=1&l=2&s=sw&tier=ksf$/);
  h.ids.srcs.children[0].events.click(); h.winEvents.hashchange();
  await reply('ranked', null, 'clean', 1, 2);
  assert.match(h.ids.empty.textContent, /for WOS yet.*CS:S.*Momentum/);
  route('#m=surf_fixture&s=tas');
  await reply('community', 'TAS runner', 'tas');
  assert.match(h.ids.srcs.textContent, /assisted/);
  route('#m=surf_fixture&tier=combined');
  await reply('combined', 'Legacy combined runner');
  assert.match(h.context.location.hash, /tier=combined$/);
  assert.match(h.ids.srcs.textContent, /All games/);
  console.log('PASS source boards: WOS default, CS:S/Momentum opt-in, TAS, source-specific styles and legacy links');
}
async function peopleSources() {
  const h = harness('surfd/web/board.js');
  const route = hash => { h.context.location.hash = hash; h.winEvents.hashchange(); };
  const player = { who: 'abc123def456', name: 'Multi-source player', n: 991, ranked: 3, mom: 980, ksf: 8 };
  const result = (source, n = 1) => ({ source, n, players: n ? [player] : [] });
  h.context.location.hash = '#who=';
  h.events.DOMContentLoaded();
  assert.equal(h.requests.at(-1).url, 'api/players?source=ranked');
  h.requests.at(-1).resolve(result('ranked')); await tick();
  assert.match(h.ids['people-list'].textContent, /3 times/);
  assert.doesNotMatch(h.ids['people-list'].textContent, /991/);
  assert.equal(h.ids.playersources.children[0].getAttribute('aria-pressed'), 'true');
  assert.deepEqual(h.ids.playersources.children.map(b => b.textContent), ['WOS', 'CS:S (KSF)', 'Momentum Mod']);
  h.ids.pq.value = 'Multi';
  h.ids.playersources.children[1].events.click(); h.winEvents.hashchange();
  assert.equal(h.requests.at(-1).url, 'api/players?source=ksf&q=Multi');
  h.requests.at(-1).resolve(result('ksf')); await tick();
  assert.match(h.ids['people-list'].textContent, /8 times/);
  const profile = h.ids['people-list'].children[0].children[0].href;
  route(profile);
  assert.equal(h.ids.playersback.href, '#who=Multi&source=ksf');
  assert.equal(h.requests.at(-1).url, 'api/player/abc123def456');
  route(h.ids.playersback.href);
  const old = h.requests.at(-1);
  h.ids.playersources.children[2].events.click(); h.winEvents.hashchange();
  assert.equal(h.requests.at(-1).url, 'api/players?source=momentum&q=Multi');
  h.requests.at(-1).resolve(result('momentum')); await tick();
  old.resolve(result('ksf')); await tick();
  assert.match(h.ids['people-list'].textContent, /980 times/);
  h.ids.pq.value = 'missing player'; h.ids.pq.events.input(); h.timer(220); h.winEvents.hashchange();
  assert.equal(h.requests.at(-1).url, 'api/players?source=momentum&q=missing%20player');
  h.requests.at(-1).resolve(result('momentum', 0)); await tick();
  assert.match(h.ids.psummary.textContent, /No Momentum Mod players match/);
  route('#who=&source=bad');
  assert.equal(h.requests.at(-1).url, 'api/players?source=ranked');
  h.requests.at(-1).resolve({ n: 1, players: [player] }); await tick();
  assert.equal(h.ids['people-list'].children.length, 0, 'refuse a legacy mixed response');
  assert.match(h.ids.err.textContent, /source filter is unavailable/);
  console.log('PASS player directory: filtered requests, source counts, deep links, search and stale responses');
}
async function zoning() {
  const h = harness('src/release/site/zoning.js');
  h.requests[0].resolve({ made: '2026-01-01', cell: [1, 1, 2, 2], rows: [
    { n: 'surf_case', s: -1, t: 1, m: '', k: '', p: 1, z: 2, b: 0 },
    { n: 'surf_other', s: -1, t: 2, m: 'Mapper', k: '', p: 2, z: 2, b: 0 }
  ] }); await tick();
  const avail = h.requests.find(r => r.url === 'board/api/availability');
  assert.ok(h.requests.find(r => r.url.endsWith('/history')), 'history starts before availability resolves');
  assert.ok(avail);
  h.events.visibilitychange();
  assert.equal(h.requests.filter(r => r.url === 'board/api/availability').length, 1, 'no overlapping poll');
  avail.resolve({ v: 1, t: 1, maps: [{ map: 'Surf_Case', have: 1 }] }); await tick(); h.timer(0);
  assert.equal(h.ids.zlist.children.length, 1, 'done excluded');
  h.ids.zdone.checked = true; h.ids.zdone.events.change(); h.timer(0);
  assert.equal(h.ids.zlist.children.length, 2);
  const first = h.ids.zlist.children[0];
  assert.equal(h.ids.zlist.children[1].children[3].children[0].href, 'map/Surf_Case', 'download keeps canonical casing');
  h.timer(60000);
  h.requests.filter(r => r.url === 'board/api/availability')[1].resolve({ v: 1, t: 2, maps: [{ map: 'Surf_Case', have: 1 }] });
  await tick(); h.timer(0);
  assert.equal(h.ids.zlist.children[0], first, 'unchanged availability preserves rows');
  assert.equal(h.requests.filter(r => r.url.endsWith('/history')).length, 1, 'no overlapping history');
  h.ids.zq.value = 'mapper'; h.ids.zq.events.input(); h.timer(150); h.timer(0);
  assert.equal(h.ids.zlist.children.length, 1);
  h.timer(60000); h.requests.filter(r => r.url === 'board/api/availability')[2].reject(Error('offline'));
  await tick(); h.timer(0);
  assert.equal(h.ids.zlist.children.length, 1, 'failure preserves catalogue and controls');
  assert.match(h.ids.znote.textContent, /unavailable/);
  console.log('PASS zoning: independent history, overlap guards, unchanged row identity, debounce and offline preservation');
}
async function zoningHistory() {
  const h = harness('src/release/site/zoning.js');
  h.requests[0].resolve({ made: '2026-01-01', cell: [1, 1, 2, 2], rows: [
    { n: 'surf_case', s: -1, t: 1, m: '', k: '', p: 1, z: 2, b: 0 }
  ] }); await tick();
  h.requests.find(r => r.url === 'board/api/availability').resolve({ v: 1, t: 1,
    maps: [{ map: 'Surf_Case', have: 0 }] });
  await tick(); h.timer(0);
  assert.equal(h.ids.zlist.children[0].children[3].children[0].href, 'map/Surf_Case',
    'incomplete map keeps canonical BSP spelling from have=0 metadata');
  h.requests.find(r => r.url.endsWith('/history')).resolve({ ok: true, now: 100,
    rows: [{ map: 'Surf_Case', kind: 'publish', at: 90, by: 'Synthetic' }] });
  await tick(); h.timer(0);
  assert.equal(h.ids.zlist.children.length, 0, 'resolved history marks published map done');
  assert.match(h.ids.zstats.textContent, /1 zoned/);
  h.ids.zdone.checked = true; h.ids.zdone.events.change(); h.timer(0);
  assert.match(h.ids.zlist.children[0].className, /done/);
  h.timer(60000);
  h.requests.filter(r => r.url === 'board/api/availability')[1].reject(Error('offline'));
  await tick(); h.timer(0);
  assert.match(h.ids.zlist.children[0].className, /done/, 'live failure retains prior zoned status');
  h.requests.filter(r => r.url.endsWith('/history'))[1].resolve({ ok: true, now: 120,
    rows: [{ map: 'Surf_Case', kind: 'rollback', at: 110, by: 'Synthetic' }] });
  await tick(); h.timer(0);
  assert.doesNotMatch(h.ids.zlist.children[0].className, /done/, 'resolved rollback removes history-only completion');
  assert.match(h.ids.zstats.textContent, /1 map to zone/);
  console.log('PASS zoning history: have=0 canonical names, publication, offline last-good status and rollback');
}
(async () => {
  if (!process.argv.includes('--zoning-only')) { await board(); await boardSources(); await peopleSources(); }
  await zoning(); await zoningHistory();
})().catch(e => { console.error(e); process.exitCode = 1; });
