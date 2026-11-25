#!/usr/bin/env python3
"""P1834 source-body acting scheduler test; --emit-vm also writes a standalone QC fixture.

C++ translation is preliminary, NOT a QC build/VM or native socket/filesystem test.
The emitted QC uses qclib qcvm's puts builtin (#1). Parent must compile/run it under
its game lock. Filesystem operations are mocked; production iterator/guard bodies
are extracted, not reimplemented. No installed data or runtime is touched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = {
    'src/server/sv_lobby.qc': ['Lobby_IdleEmpty', 'Lobby_DeferredMaintenance', 'Lobby_HeartbeatPeriod', 'Lobby_HeartbeatDue', 'Lobby_HeartbeatAnswered', 'Lobby_Heartbeat', 'URI_Get_Callback'],
    'src/server/sv_resume.qc': ['SV_MsSweepStep'],
    'src/server/sv_timer.qc': ['SV_EvidenceSweepStep'],
    'src/server/sv_main.qc': ['SV_IdleMaintenanceFrame'],
}


def extract(text, name):
    m = re.search(r'^(float|void)\([^\n]*\) ' + name + r' =\s*\{', text, re.M)
    if not m:
        raise ValueError(name)
    # These selected bodies have no braces within quoted strings/comments.
    end, depth = m.end(), 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[m.start():end] + ';\n'


PRE = r'''
#define TRUE 1
#define FALSE 0
#define FS_NAMESORT 1
#define ACCT_ID_BASE 8000000
#define TF_CHEAT 1
#define TF_NOPROFILE 2
// Standalone fixture ABI markers only: no engine-visible globals/fields.
void end_sys_globals;
void end_sys_fields;
void(string s) puts = #1;
float time, active, reserved, occupants, fast, maintenance, rate;
float master, zone_entsready, zone_loaded;
float lobby_hb_ready, lobby_hb_pending, lobby_map_pending;
float lobby_run_waiting, lobby_hb_seen, lobby_hb_lastcode;
float sends, wire_due, wire_id, directed;
float lobby_hb_id, lobby_hb_sent, lobby_hb_next, lobby_hb_last, lobby_hb_ready_sent, lobby_map_ready;
float sv_maint_pending, sv_maint_next, sv_maint_resume_done;
float ms_maint_root, ms_maint_open, ms_maint_handle, ms_maint_index;
float ev_maint_phase, ev_maint_open, ev_maint_handle, ev_maint_index, ev_maint_native_done;
string ev_maint_day, mapname;
float scans, entries, closes, all_scans, stamps, metadata, scan_size, owner, disabled;
float last_profile, profile_hits[7];
float(string a, string b) strcmp = #11;
float(string s) strlen = { return s != ""; };
float() Tour_Owns = { return reserved; };
float() Tour_Occupants = { return occupants; };
float() Lobby_Active = { return active; };
void(string n, string v) registercvar = {};
float(string n) cvar =
{
 if (n == "lobby_run_probe") return 0;
 if (n == "lobby_empty_fast") return fast;
 if (n == "lobby_idle_maintenance") return maintenance;
 if (n == "lobby_master_rate") return rate;
 if (n == "run_evidence_sweepall") return owner;
 if (disabled) return 0;
 return 14;
};
string(string n) cvar_string = { if (master) return "local-test-master"; return ""; };
string(string n) serverkey = { return ""; };
string(float utc, string fmt) strftime = { return "20261125"; };
string(entity e, string n) infokey = { if (stamps) return "20261125"; return ""; };
entity world;
void(string s) localcmd = { stamps = stamps + 1; };
float(float n) gettime = { return time; };
string(string fmt, ...) sprintf = { return fmt; };
void(string s) dprint = {};
void(string s) print = {};
float(__variant f) checkbuiltin = { return 1; };
void(entity e, float n, string s, string kind) held_metadata = { metadata = metadata + 1; };
string(string s) strzone = { return s; };
void(string s) strunzone = {};
float(string p) FS_MovementProfileKnown = { return 1; };
string(string p, string path) FS_MovementProfilePath =
{
 last_profile = 0;
 if (p == "ag-100-v1") last_profile = 1;
 if (p == "ag-250-v1") last_profile = 2;
 if (p == "ag-1000-v1") last_profile = 3;
 if (p == "cs16-v1") last_profile = 4;
 if (p == "hl2-pre-v1") last_profile = 5;
 if (p == "hl2-post-v1") last_profile = 6;
 profile_hits[last_profile] = profile_hits[last_profile] + 1;
 return path;
};
float(string pat, float sort, float quiet) search_begin =
{
 scans = scans + 1;
 if (pat == "data/evidence/*/*.*") all_scans = all_scans + 1;
 return scans - 1; // handle 0 is valid
};
float(float h) search_getsize = { return scan_size; };
string(float h, float i) search_getfilename = { return "fixture-entry"; };
void(float h) search_end = { closes = closes + 1; };
void(string profile, string fn) SV_MsSweepOne = { entries = entries + 1; };
void(string fn) SV_EvidenceSweepOne = { entries = entries + 1; };
'''

TRANSPORT = r'''
// Explicit mocks: no socket, authentication, board or directed-name parser.
// Actual directed-name/native-slot guards have their own source-body test.
void() Lobby_BoardState = {};
entity(entity e) SV_PlNext = { return world; };
void(entity e, float a, float b, float c, float d) Lobby_SubmitStage = {};
void(entity e, float a, float b, float c, float d, string f, float g, float h) Lobby_SubmitRun = {};
void(string k, string v) cvar_set = {};
string(string s) uri_escape = { return s; };
string(string a, string b) strcat = { return a; };
float() Lobby_PlayerCount = { return occupants; };
float(string u, float id, string mime, string body) uri_post =
{
 sends = sends + 1; wire_due = time + 1.2; wire_id = id;
 return TRUE;
};
float(float id, float code, string body) PublicTime_Reply = { return FALSE; };
float(float id, float code, string body) PlayStats_Reply = { return FALSE; };
float(float id, float code, string body) SV_TASShareReply = { return FALSE; };
float(float id, float code, string body) Inv_SVReply = { return FALSE; };
float(float id, float code, string body) VM_SVReply = { return FALSE; };
float(float id, float code, string body) Social_Reply = { return FALSE; };
float(float id, float code, string body) Tour_Reply = { return FALSE; };
void(float id, float code, string body) Account_Reply = {};
void(float id, float code, string body) Lobby_RunReply = {};
float(string body) Lobby_Directed =
{
 if (body != "map fixture") return FALSE;
 if (!reserved && !occupants) { lobby_map_pending = time + 1; directed = directed + 1; }
 return TRUE;
};
'''

TESTS = r'''
float failures, checks;
void(float ok, string msg) check =
{
 checks = checks + 1;
 if (!ok) { puts("FAIL "); puts(msg); puts("\n"); failures = failures + 1; }
};
void() main =
{
 local float i, before, oldentries, pending_entries, replies;
 active = maintenance = fast = 1; rate = 5; time = 10;
 check(Lobby_HeartbeatPeriod() == 1, "empty opted-in heartbeat 1s acts");
 occupants = 1;
 check(Lobby_HeartbeatPeriod() == 5, "connecting/native spectator occupant restores active rate");
 occupants = 0; reserved = 1;
 check(Lobby_HeartbeatPeriod() == 5, "reservation guard");
 reserved = 0; rate = 19; fast = 0;
 check(Lobby_HeartbeatPeriod() == 19, "explicit slow custom rate unchanged without opt-in");
 fast = 1;
 check(Lobby_HeartbeatPeriod() == 1, "explicit policy may accelerate empty custom rate");
 active = 0;
 check(Lobby_HeartbeatPeriod() == 19, "disabled lobby unchanged");
 check(!Lobby_DeferredMaintenance(), "disabled lobby retains synchronous init");
 active = 1; maintenance = 0;
 check(!Lobby_DeferredMaintenance(), "custom/listen default retains synchronous init");
 maintenance = 1;
 check(Lobby_DeferredMaintenance(), "ordinary maintenance opt-in acts");
 rate = 0; fast = 0;
 check(Lobby_HeartbeatPeriod() == 5, "invalid rate fallback");
 rate = 99;
 check(Lobby_HeartbeatPeriod() == 25, "rate cap unchanged");
 fast = 1; rate = 5;
 lobby_map_pending = 11;
 check(Lobby_HeartbeatPeriod() == 5, "accepted map command blocks empty acceleration");
 lobby_map_pending = 0;
 // Acting send-deadline/one-outstanding control; no repeated frame may enqueue.
 check(Lobby_HeartbeatDue(), "first heartbeat due");
 check(!Lobby_HeartbeatDue(), "no duplicate in same frame");
 time = 11;
 check(!Lobby_HeartbeatDue(), "slow HTTP request does not stampede");
 lobby_hb_pending = 0;
 check(Lobby_HeartbeatDue(), "empty next send at 1s");
 lobby_hb_pending = 0; occupants = 1; time = 12;
 check(!Lobby_HeartbeatDue(), "arriving occupant restores active deadline immediately");
 time = 16;
 check(Lobby_HeartbeatDue(), "active 5s deadline acts");
 occupants = 0; lobby_hb_pending = 0;
 // Callback loss has a bounded replacement cadence; old replies cannot authorize a move.
 lobby_hb_id = 4; time = 41;
 check(Lobby_HeartbeatDue(), "lost callback recovers at 25s");
 lobby_hb_id = 6;
 check(!Lobby_HeartbeatAnswered(4) && lobby_hb_pending, "late old reply cannot clear current request or direct map");
 check(Lobby_HeartbeatAnswered(6) && !lobby_hb_pending, "matching success/error callback clears pending");
 check(!Lobby_HeartbeatAnswered(6), "duplicate callback rejected");
 time = 41.5;
 check(!Lobby_HeartbeatDue(), "enqueue failure/reply cannot bypass 1s empty deadline");
 time = 42;
 check(Lobby_HeartbeatDue(), "normal cadence resumes after recovered callback");
 lobby_hb_pending = 0;
 // No scan at init or before readiness/ack; a native occupant/reservation blocks.
 sv_maint_pending = 1; master = 0; scan_size = 3;
 SV_IdleMaintenanceFrame(); check(scans == 0, "before entity/zone readiness");
 zone_entsready = zone_loaded = 1; master = 1;
 SV_IdleMaintenanceFrame(); check(scans == 0, "before successful ready heartbeat");
 lobby_hb_ready = 1; lobby_hb_pending = 1;
 SV_IdleMaintenanceFrame(); check(scans == 0, "outstanding master request blocks maintenance");
 lobby_hb_pending = 0; occupants = 1;
 SV_IdleMaintenanceFrame(); check(scans == 0, "native occupant blocks maintenance");
 occupants = 0; reserved = 1;
 SV_IdleMaintenanceFrame(); check(scans == 0, "reserved empty server blocks maintenance");
 reserved = 0; lobby_map_pending = time + 1;
 SV_IdleMaintenanceFrame(); check(scans == 0, "map command blocks maintenance");
 lobby_map_pending = 0;
 SV_IdleMaintenanceFrame();
 check(scans == 1 && entries == 0 && ms_maint_open, "first idle turn opens one search only");
 SV_IdleMaintenanceFrame(); check(scans == 1 && entries == 0, "no same-frame drain");
 occupants = 1; time = time + 1;
 SV_IdleMaintenanceFrame(); check(entries == 0 && closes == 0, "occupied pause preserves iterator");
 occupants = 0;
 SV_IdleMaintenanceFrame(); check(entries == 1 && scans == 1, "resume one result only");
 // Whole-tree owner opt-in; all 7 roots, exact scan/result bounds per turn.
 owner = 1;
 for (i = 0; i < 120; i = i + 1)
 {
  time = time + 0.2; before = scans; oldentries = entries;
  SV_IdleMaintenanceFrame();
  check(scans - before <= 1 && entries - oldentries <= 1, "one scan OR result per turn");
  check(!(scans > before && entries > oldentries), "scan never drains results in same turn");
 }
 check(!sv_maint_pending, "pending work eventually completes in idle windows");
 check(scans == 9 && closes == 9 && entries == 27, "all 7 resume roots plus map/all evidence processed");
 check(stamps == 1 && all_scans == 1, "designated whole-tree owner stamps only completion");
 for (i = 0; i < 7; i = i + 1) check(profile_hits[i] == 1, "each original root scanned exactly once");
 // A non-owner gets only map evidence, offline is explicitly allowed post-ready.
 ev_maint_phase = ev_maint_open = 0; sv_maint_pending = 1;
 owner = master = 0; before = scans;
 for (i = 0; i < 12; i = i + 1) { time = time + 0.2; SV_IdleMaintenanceFrame(); }
 check(!sv_maint_pending && scans == before + 1, "offline/no-master map-only queue completes");
 check(all_scans == 1 && stamps == 1, "non-owner cannot sweep/stamp whole tree");
 // Revocation closes an already-open all-tree iterator without processing another result.
 ev_maint_phase = 1; ev_maint_open = 0; owner = 1; stamps = 0;
 SV_EvidenceSweepStep(); SV_EvidenceSweepStep(); before = entries; owner = 0;
 SV_EvidenceSweepStep();
 check(entries == before && stamps == 0 && !ev_maint_open, "owner revocation blocks deletion and completion stamp");
 // Native policy still acts for map/all when ordinary evidence expiry is disabled.
 ev_maint_phase = ev_maint_open = ev_maint_native_done = 0;
 owner = disabled = 1; stamps = 0; before = metadata; oldentries = scans;
 for (i = 0; i < 8; i = i + 1) SV_EvidenceSweepStep();
 check(metadata == before + 2 && scans == oldentries && stamps == 1, "native policy independent of disabled evidence expiry");
 // Regression: drive the actual heartbeat, callback and maintenance bodies in
 // StartFrame's extracted production order, not a hand-ordered scheduler.
 // Transport ACKs consistently arrive at 1.2s (> the empty 1s send period).
 ms_maint_root = ms_maint_open = ms_maint_index = 0;
 ev_maint_phase = ev_maint_open = ev_maint_index = ev_maint_native_done = 0;
 sv_maint_resume_done = sv_maint_next = 0; sv_maint_pending = 1;
 scans = entries = closes = all_scans = stamps = metadata = 0;
 lobby_hb_sent = lobby_hb_pending = lobby_hb_ready = lobby_map_pending = 0;
 lobby_map_ready = zone_loaded = zone_entsready = 1;
 active = maintenance = fast = owner = master = 1; disabled = occupants = reserved = 0;
 sends = wire_due = wire_id = directed = replies = 0; rate = 5; time = 100;
 for (i = 0; i < 7; i = i + 1) profile_hits[i] = 0;
 for (i = 0; i < 1800; i = i + 1)
 {
  time = 100 + i * 0.05;
  if (wire_due && time >= wire_due)
  {
   wire_due = 0;
   URI_Get_Callback(wire_id, 0, "ok");
   replies = replies + 1;
  }
  pending_entries = entries; before = scans; oldentries = metadata;
  if (lobby_hb_pending)
  {
   P1834_ProductionFrame();
   check(entries == pending_entries && scans == before && metadata == oldentries, "pending slow request blocks retention");
  }
  else P1834_ProductionFrame();
 }
 check(replies > 40 && sends > 40, "repeated >period successful callbacks acted");
 check(!sv_maint_pending && scans == 9 && entries == 27 && closes == 9 && metadata == 2, "slow successful ACKs cannot starve any retention phase");
 check(stamps == 1, "slow-ACK queue stamps completed whole-tree work");
 // A successful directed reply blocks the pre-enqueue opportunity too.
 sv_maint_pending = 1; sv_maint_resume_done = 0; ms_maint_root = 0;
 time = time + 2; lobby_hb_pending = 1; lobby_hb_ready_sent = 1;
 URI_Get_Callback(lobby_hb_id, 0, "map fixture");
 before = scans; oldentries = metadata; pending_entries = entries;
 P1834_ProductionFrame();
 check(directed == 1 && lobby_map_pending > time, "successful directed callback arms map barrier");
 check(scans == before && entries == pending_entries && metadata == oldentries, "map barrier blocks pre-enqueue maintenance");
 if (!failures) puts("PASS P1834 scheduling/guard/queue source-body checks\n");
};
'''

CPP_PRE = r'''
#include <string>
#include <iostream>
#include <cstring>
using string = std::string;
using entity = int;
void puts(string s) { std::cout << s; }
double strcmp(string a, string b) { return a.compare(b); }
'''


def cpp(qc):
    qc = re.sub(r'^void end_sys_(?:globals|fields);\n', '', qc, flags=re.M)
    qc = re.sub(r'^void\(string s\) puts = #1;\n', '', qc, flags=re.M)
    qc = re.sub(r'^float\(string a, string b\) strcmp = #11;\n', '', qc, flags=re.M)
    qc = re.sub(r'^((?:float|void|string|entity))\(([^\n]*)\) (\w+) =', r'\1 \3(\2)', qc, flags=re.M)
    qc = re.sub(r'\blocal\s+', '', qc)
    qc = qc.replace('__variant', 'double')
    qc = re.sub(r'profile_hits\[([^0-9][^]]*)\]', r'profile_hits[(int)(\1)]', qc)
    qc = re.sub(r'\bfloat\b', 'double', qc)
    qc = qc.replace('double time,', 'double testtime,')
    qc = re.sub(r'\btime\b', 'testtime', qc)
    qc = qc.replace('if (!failures) puts(', 'if (!failures) puts(')
    qc = qc.replace('void main()', 'void run_tests()')
    qc = qc.replace('checkbuiltin(held_metadata)', 'checkbuiltin(0)')
    qc = qc.replace('reqid & 1', '(int)reqid & 1')
    qc = qc.replace('pflags | TF_NOPROFILE', '(int)pflags | TF_NOPROFILE')
    return CPP_PRE + qc + '\nint main() { run_tests(); return failures ? 1 : 0; }\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=ROOT / 'rig/lobbyfast/source-body')
    ap.add_argument('--emit-vm', action='store_true')
    ap.add_argument('--mutate', choices=['occupancy', 'ready', 'owner', 'drain', 'heartbeat-first'])
    args = ap.parse_args()
    out = args.out.resolve()
    if ROOT not in out.parents or out.exists():
        ap.error('--out must be a fresh directory within this worktree')
    out.mkdir(parents=True)
    bodies = '\n'.join(extract((ROOT / path).read_text(), name)
                       for path, names in FUNCTIONS.items() for name in names)
    if args.mutate and args.mutate != 'heartbeat-first':
        old, new = {
            'occupancy': ('if (Tour_Occupants() == 0)', 'if (TRUE)'),
            'ready': ('if (!zone_entsready || !zone_loaded) return;', ''),
            'owner': ('if (ev_maint_phase == 0 || cvar("run_evidence_sweepall"))', 'if (TRUE)'),
            'drain': ('ms_maint_index = ms_maint_index + 1;', 'ms_maint_index = ms_maint_index + 2;'),
        }[args.mutate]
        assert bodies.count(old) == 1
        bodies = bodies.replace(old, new)
    # Ordering/source integration contracts supplement the acting extracted functions.
    main_source = (ROOT / 'src/server/sv_main.qc').read_text()
    timer_source = (ROOT / 'src/server/sv_timer.qc').read_text()
    assert 'if (Lobby_DeferredMaintenance())\n\t\tsv_maint_pending = TRUE;\n\telse\n\t\tSV_MsSweep();' in main_source
    assert 'if (!Lobby_DeferredMaintenance())\n\t\tSV_EvidenceSweep();' in timer_source
    order = re.search(r'\t(?:Lobby_Heartbeat|SV_IdleMaintenanceFrame)\(\);\n\t(?:Lobby_Heartbeat|SV_IdleMaintenanceFrame)\(\);', main_source)
    assert order, 'production adjacent scheduling seam not found'
    assert main_source.index('SV_ZoneFrame();') < order.start()
    frame_body = order.group(0)
    if args.mutate == 'heartbeat-first':
        frame_body = '\tLobby_Heartbeat();\n\tSV_IdleMaintenanceFrame();'
    frame = 'void() P1834_ProductionFrame = {\n' + frame_body + '\n};\n'
    qc = PRE + TRANSPORT + bodies + frame + TESTS
    (out / 'unit.cpp').write_text(cpp(qc))
    if args.emit_vm:
        (out / 'unit.qc').write_text(qc)
        (out / 'progs.src').write_text('progs.dat\nunit.qc\n')
    results = []
    for label, cmd in [('compile', ['c++', '-std=c++17', '-O0', str(out / 'unit.cpp'), '-o', str(out / 'acting')]),
                       ('acting', [str(out / 'acting')])]:
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        (out / (label + '.log')).write_text(result.stdout)
        results.append({'command': cmd, 'exit': result.returncode})
        print(label, 'exit', result.returncode)
        print(result.stdout, end='')
        if result.returncode:
            break
    manifest = {'commands': results, 'mutate': args.mutate,
                'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'sources': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FUNCTIONS},
                'limits': 'C++ translated source bodies with mocked native occupancy, HTTP and FS. '
                          'QC fixture emitted only, NOT compiled/run here. Entry deletion/parser functions stubbed. '
                          'Directed dispatch is mocked; separate directed tests act its parser with synthetic native slots. '
                          'Does not prove scan latency, native clienttype semantics or socket heartbeat latency.'}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    raise SystemExit(results[-1]['exit'])


if __name__ == '__main__':
    main()
