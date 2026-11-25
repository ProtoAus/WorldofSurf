#!/usr/bin/env python3
"""Act production directed-map/native occupancy guards with synthetic native slots.

No game/runtime socket: clienttype is mocked to the native builtin's documented
classification (REAL includes connected-but-unspawned and spectator clients).
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from test_p1834_lobby_idle import ROOT, extract
from test_p1834_lobby_retention import translate

PRE = r'''
#include <string>
#include <iostream>
#include <algorithm>
using string=std::string;
using entity=int;
#define TRUE 1
#define FALSE 0
#define TQ_CLIENT_MAX 256
#define CLIENTTYPE_REAL 1
#define CLIENTTYPE_BOT 2
#define CLIENTTYPE_NOTACLIENT 3
string mapname="surf_fixture";
double testtime=10,lobby_map_pending,reserved;
int commands,slots[4];
string command;
entity edict_num(double n){return n;}
double clienttype(entity n){return n>3?3:slots[n];}
double Tour_Owns(){return reserved;}
double strlen(string s){return s.size();}
double str2chr(string s,double n){return s.at((int)n);}
string substring(string s,double start,double count){return s.substr((int)start,(int)count);}
string strtolower(string s){std::transform(s.begin(),s.end(),s.begin(),[](unsigned char c){return std::tolower(c);});return s;}
string sprintf(string fmt,string s){auto p=fmt.find("%s");if(p!=string::npos)fmt.replace(p,2,s);return fmt;}
string sprintf(string fmt,string a,string b){return sprintf(sprintf(fmt,a),b);}
string sprintf(string fmt,double n){return fmt;}
void print(string s){}
void localcmd(string s){commands++;command=s;}
'''
POST = r'''
int main(){
 for(int kind: {1,2}) {
  // REAL is used for spawned, connecting and spectator native slot fixtures.
  for(int population: {1,2,3}) {
   slots[population]=kind;commands=0;lobby_map_pending=0;
   if(!Lobby_Directed("map surf_destination") || commands || lobby_map_pending){std::cerr<<"FAIL occupied directed guard\n";return 1;}
   slots[population]=0;
  }
 }
 reserved=1;commands=0;Lobby_Directed("map surf_destination");
 if(commands){std::cerr<<"FAIL tournament reservation guard\n";return 1;}
 reserved=0;
 for(string bad:{"map ../escape","map surf_x;quit","map -x","map  surf_x","map .","map a/b"}) {
  Lobby_Directed(bad);if(commands){std::cerr<<"FAIL map name validation\n";return 1;}
 }
 if(Lobby_Directed("ok") || commands){std::cerr<<"FAIL noninstruction\n";return 1;}
 Lobby_Directed("map SURF_FIXTURE");if(commands){std::cerr<<"FAIL same map\n";return 1;}
 Lobby_Directed("map surf_destination\n");
 if(commands!=1 || command!="changelevel surf_destination\n" || lobby_map_pending!=11){std::cerr<<"FAIL idle directed action control\n";return 1;}
 std::cout<<"PASS directed-map actual native-slot walk/occupied/reserved/validation guards and empty action control\n";
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    out = a.out.resolve()
    if ROOT not in out.parents or out.exists():
        ap.error('--out must be fresh within this worktree')
    out.mkdir(parents=True)
    lobby = (ROOT / 'src/server/sv_lobby.qc').read_text()
    tour = (ROOT / 'src/server/sv_tournament.qc').read_text()
    bodies = extract(tour, 'Tour_Occupants') + extract(lobby, 'Lobby_MapNameOK') + extract(lobby, 'Lobby_Directed')
    bodies = translate(bodies).replace('time + 1', 'testtime + 1')
    (out / 'directed.cpp').write_text(PRE + bodies + POST)
    results = []
    for label, cmd in [('compile', ['c++', '-std=c++17', '-O0', str(out / 'directed.cpp'), '-o', str(out / 'acting')]),
                       ('acting', [str(out / 'acting')])]:
        r = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        (out / (label + '.log')).write_text(r.stdout)
        results.append({'command': cmd, 'exit': r.returncode})
        print(label, 'exit', r.returncode, '\n' + r.stdout, end='')
        if r.returncode:
            break
    (out / 'manifest.json').write_text(json.dumps({'commands': results, 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT / 'src/server/sv_lobby.qc', ROOT / 'src/server/sv_resume.qc', ROOT / 'src/server/sv_timer.qc']},
        'limits': 'Synthetic native-slot classes, exact QC function bodies translated to C++; no real connecting client/socket.'}, indent=2) + '\n')
    raise SystemExit(results[-1]['exit'])


if __name__ == '__main__':
    main()
