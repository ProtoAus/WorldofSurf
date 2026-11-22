#!/usr/bin/env python3
"""P1737: report points for the prederror reports sent before the ledger existed.

Reads every lobby report (FTESURF-PREDERR 1, data/prederr/<map>_<utc>_p<port>_s<slot>.txt) under the given
directories, once per file name (the Pi's copy and any fetched copies are the same report), and writes the
ledger lines sv_prederr.qc SV_PePoint writes -- "<account> <utc> <map>" -- for the ones whose header names an
8-hex account.  Install the output as the lobbies' data/reportpoints/seed.txt.

    python3 -I tools/p1737_seed.py OUT DIR [DIR ...]
"""
import os
import re
import sys

HEX8 = re.compile(r"[0-9a-f]{8}")


def header(path):
    acct = utc = mapname = None
    with open(path, "rb") as fh:
        head = fh.read(4096).decode("latin-1", "replace").splitlines()
    if not head or head[0].strip() != "FTESURF-PREDERR 1":
        return None
    for line in head[1:12]:
        if line.startswith("player "):
            m = re.search(r" account (\S*) ", line + " ")
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
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out, dirs = sys.argv[1], sys.argv[2:]
    seen, lines, skipped = set(), [], 0
    for d in dirs:
        for root, _dirs, files in os.walk(d):
            for name in sorted(files):
                if not re.fullmatch(r".+_\d{8}_\d{6}_p\d+_s\d+\.txt", name) or name in seen:
                    continue
                seen.add(name)
                row = header(os.path.join(root, name))
                if row is None:
                    skipped += 1
                    continue
                lines.append(row)
    lines.sort(key=lambda r: r.split(" ")[1])
    with open(out, "w", encoding="ascii", newline="\n") as fh:
        fh.write("".join(r + "\n" for r in lines))
    counts = {}
    for r in lines:
        counts[r.split(" ")[0]] = counts.get(r.split(" ")[0], 0) + 1
    print("%d reports (%d distinct files, %d without an account or header); %d accounts: %s"
          % (len(lines), len(seen), skipped, len(counts),
             ", ".join("%s %d" % kv for kv in sorted(counts.items(), key=lambda kv: -kv[1]))))


if __name__ == "__main__":
    main()
