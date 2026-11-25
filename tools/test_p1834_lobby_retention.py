#!/usr/bin/env python3
"""Act exact P1834 retention predicates against pinned original sweep bodies.

C++ source-body adapter only, mocked FS/meta parser. No native/QC runtime, data
files or actual deletion. Compares legacy/subject deletion intent with fixtures
for each expiry boundary, known/unknown profile, claimed leaf and protection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from test_p1834_lobby_idle import ROOT, extract

BASE = 'f8d04f241d0e70c49bcb33faae6eb709766844af'
PRE = r'''
#include <string>
#include <vector>
#include <iostream>
#include <algorithm>
using string = std::string;
#define TRUE 1
#define FALSE 0
#define FS_NAMESORT 1
string mapname = "surf_fixture";
double days=14, ms_day;
std::vector<string> files, removed;
double strcmp(string a,string b) { return a.compare(b); }
double strlen(string s) { return s.size(); }
double str2chr(string s,double n) { return s.at((int)n); }
string substring(string s,double a,double n) { return s.substr((int)a,(int)n); }
string strcat(string a,string b) {return a+b;}
string sprintf(string fmt,string s) {auto p=fmt.find("%s"); if(p!=string::npos)fmt.replace(p,2,s);return fmt;}
string sprintf(string fmt,string s,double n) {return fmt;}
string strftime(double utc,string fmt) {return "00000100";}
double FS_DayNumOf(string s) { if(s.size()!=8 || s.find_first_not_of("0123456789")!=string::npos)return -1; return std::stoi(s); }
double cvar(string n) {return days;}
double FS_MovementProfileKnown(string p) {return p!="unknown";}
string FS_MovementProfilePath(string p,string path) {return path;}
double SV_MsReadMeta(string path) {
 if(path.find("badmeta")!=string::npos)return 0;
 ms_day=0;
 if(path.find("expired")!=string::npos)ms_day=85;
 if(path.find("boundary")!=string::npos)ms_day=86;
 if(path.find("fresh")!=string::npos)ms_day=99;
 return 1;
}
double SV_MsSweepProtected(string dir) {return dir.find("protected")!=string::npos;}
double SV_MsSlotCleanMain(string path) {return path.find("unclean")==string::npos;}
void SV_MsWipeDirProfile(string dir,string leaf,string profile) {removed.push_back(profile+":"+dir+leaf);}
double search_begin(string pat,double sort,double quiet) {return 0;}
double search_getsize(double h) {return files.size();}
string search_getfilename(double h,double i) {return files.at((int)i);}
void search_end(double h) {}
void fremove(string fn) {removed.push_back(fn);}
double SV_DevOn() {return 0;}
void dprint(string s) {}
'''
POST = r'''
int main() {
 int checks=0;
 std::vector<string> resume={
  "data/resume/surf_fixture/@expired/save000/ms.txt",
  "data/resume/surf_fixture/@expired-protected/save000/ms.txt",
  "data/resume/surf_fixture/@expired-unclean/save000/ms.txt",
  "data/resume/surf_fixture/@boundary/save000/ms.txt",
  "data/resume/surf_fixture/@fresh/save000/ms.txt",
  "data/resume/surf_fixture/@nodate/save000/ms.txt",
  "data/resume/surf_fixture/@badmeta/save000/ms.txt",
  "data/resume/surf_fixture/@expired/save000/ms_claim.txt"};
 for (double age: {-1.,0.,1.,14.,15.}) for(string profile: {"","ag-100-v1","ag-250-v1","ag-1000-v1","cs16-v1","hl2-pre-v1","hl2-post-v1","unknown"}) {
  days=age;files=resume;removed.clear();BaselineResume(profile);auto baseline=removed;
  removed.clear();for(auto fn:files)SV_MsSweepOne(profile,fn);
  if(removed!=baseline){std::cerr<<"FAIL resume equivalence age="<<age<<" profile="<<profile<<"\n";return 1;}checks++;
 }
 days=14;removed.clear();for(auto fn:resume)SV_MsSweepOne("ag-100-v1",fn);
 if(removed.size()!=1 || removed[0].find("@expired/save000/ms.txt")==string::npos) {std::cerr<<"FAIL protected/boundary/fresh/claim fixture did not discriminate\n";return 1;}
 std::vector<string> evidence={"data/evidence/surf_fixture/00000085-run.rec","data/evidence/surf_fixture/00000085-run.rct","data/evidence/surf_fixture/00000085-run.hid","data/evidence/surf_fixture/00000086-boundary.rec","data/evidence/surf_fixture/00000099-fresh.rec","data/evidence/surf_fixture/nodate.rec"};
 for(double age:{-1.,0.,1.,14.,15.}) {
  days=age;files=evidence;removed.clear();BaselineEvidence("ignored");auto baseline=removed;
  removed.clear();for(auto fn:files)SV_EvidenceSweepOne(fn);
  if(removed!=baseline){std::cerr<<"FAIL evidence equivalence age="<<age<<"\n";return 1;}checks++;
 }
 days=14;removed.clear();for(auto fn:evidence)SV_EvidenceSweepOne(fn);
 if(removed.size()!=3){std::cerr<<"FAIL expired rec/receipt/sidecar acted\n";return 1;}
 std::cout<<"PASS retention original/subject deletion-intent equivalence "<<checks<<" arms; protected/fresh/boundary/claim controls act\n";
}
'''


def translate(qc):
    qc = re.sub(r'^((?:float|void|string|entity))\(([^\n]*)\) (\w+) =', r'\1 \3(\2)', qc, flags=re.M)
    qc = re.sub(r'\blocal\s+', '', qc)
    return re.sub(r'\bfloat\b', 'double', qc)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    out = args.out.resolve()
    if ROOT not in out.parents or out.exists():
        ap.error('--out must be fresh within this worktree')
    out.mkdir(parents=True)
    resume_path, timer_path = 'src/server/sv_resume.qc', 'src/server/sv_timer.qc'
    resume, timer = (ROOT / resume_path).read_text(), (ROOT / timer_path).read_text()
    old_resume = subprocess.check_output(['git', 'show', BASE + ':' + resume_path], cwd=ROOT, text=True)
    old_timer = subprocess.check_output(['git', 'show', BASE + ':' + timer_path], cwd=ROOT, text=True)
    source = (extract(resume, 'SV_MsSweepOne') + extract(timer, 'SV_EvidenceSweepOne')
              + extract(old_resume, 'SV_MsSweepProfile').replace('SV_MsSweepProfile =', 'BaselineResume =')
              + extract(old_timer, 'SV_EvidenceSweepPat').replace('SV_EvidenceSweepPat =', 'BaselineEvidence ='))
    (out / 'retention.cpp').write_text(PRE + translate(source) + POST)
    commands = [('compile', ['c++', '-std=c++17', '-O0', str(out / 'retention.cpp'), '-o', str(out / 'acting')]),
                ('acting', [str(out / 'acting')])]
    results = []
    for label, cmd in commands:
        r = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        (out / (label + '.log')).write_text(r.stdout)
        results.append({'command': cmd, 'exit': r.returncode})
        print(label, 'exit', r.returncode, '\n' + r.stdout, end='')
        if r.returncode:
            break
    (out / 'manifest.json').write_text(json.dumps({'base': BASE, 'commands': results, 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT / 'src/server/sv_lobby.qc', ROOT / 'src/server/sv_resume.qc', ROOT / 'src/server/sv_timer.qc']},
        'limits': 'Exact predicate bodies, mocked metadata/protection helpers/FS; no parser, native FS or QC VM certification.'}, indent=2) + '\n')
    raise SystemExit(results[-1]['exit'])


if __name__ == '__main__':
    main()
