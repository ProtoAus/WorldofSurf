#!/usr/bin/env python3
"""P1737: report points for the prederror reports sent before the ledger existed.

Reads every lobby report (FTESURF-PREDERR 1, data/prederr/<map>_<utc>_p<port>_s<slot>.txt) under the given
directories, once per file name (the Pi's copy and any fetched copies are the same report), and writes the
ledger lines sv_prederr.qc SV_PePoint writes -- "<account> <utc> <map>" -- for the finished ones ("== end" or
"== http", as the lobby credits) whose header names an 8-hex account and that began before --before (UTC
YYYYMMDD_HHMMSS: the lobbies' own ledger has every report from the deploy on).  Install the output as the
lobbies' data/reportpoints/seed.txt.  The live rule's "server rows" test is not applied: nobody had a reason to
farm a report before points existed.

    python3 -I tools/p1737_seed.py --before 20261123_120000 OUT DIR [DIR ...]
"""
import os
import re
import sys

HEX8 = re.compile(r"[0-9a-f]{8}")


def header(path):
    acct = utc = mapname = None
    with open(path, "rb") as fh:
        body = fh.read().decode("latin-1", "replace")
    head = body[:4096].split("\n")         # not splitlines: latin-1 \x85 etc. are bytes of UTF-8 names
    if not head or head[0].strip() != "FTESURF-PREDERR 1":
        return None
    if not re.search(r"^== (end|http)\r?$", body, re.M):
        return None
    for line in head[1:12]:
        if line.startswith("player "):
            m = re.search(r" slot \d+ account (\S*) ping \S*$", line)   # the fixed tail: a name may hold anything
            acct = m.group(1) if m else None
        elif line.startswith("utc "):
            m = re.match(r"utc (\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)", line)
            utc = "%s%s%s_%s%s%s" % m.groups() if m else None
        elif line.startswith("map "):
            mapname = re.sub(r"[^0-9A-Za-z._-]", "_", line[4:].strip())[:64]
    if not (acct and HEX8.fullmatch(acct) and utc and mapname):
        return None
    return "%s %s %s" % (acct, utc, mapname)


def main():
    args = sys.argv[1:]
    if len(args) < 4 or args[0] != "--before" or not re.fullmatch(r"\d{8}_\d{6}", args[1]):
        sys.exit(__doc__)
    before, out, dirs = args[1], args[2], args[3:]
    seen, lines, skipped = set(), [], 0
    for d in dirs:
        for root, _dirs, files in os.walk(d):
            for name in sorted(files):
                if not re.fullmatch(r".+_\d{8}_\d{6}_p\d+_s\d+\.txt", name) or name in seen:
                    continue
                row = header(os.path.join(root, name))
                if row is None or row.split(" ")[1] >= before:
                    skipped += 1                # a mid-upload copy may come first: the finished one still counts
                    continue
                seen.add(name)
                lines.append(row)
    lines.sort(key=lambda r: r.split(" ")[1])
    with open(out, "w", encoding="ascii", newline="\n") as fh:
        fh.write("".join(r + "\n" for r in lines))
    counts = {}
    for r in lines:
        counts[r.split(" ")[0]] = counts.get(r.split(" ")[0], 0) + 1
    print("%d reports (%d files skipped: unfinished, without an account, or from --before on); %d accounts: %s"
          % (len(lines), skipped, len(counts),
             ", ".join("%s %d" % kv for kv in sorted(counts.items(), key=lambda kv: -kv[1]))))


if __name__ == "__main__":
    main()
