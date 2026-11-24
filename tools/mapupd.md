# Map uploads (P1746): surfd/mapupd.py

An admin uploads a new map from the game (F8, `src/menu/m_mapupload.qc`); this service checks them and publishes it.
Isolated like zonepub and tasupd: its own unit, port, nginx routes and store; surfd and its DB are only read.

## Install (root, once)

From a clean checkout of the inspected commit, the installer copied to /root (it refuses to be anything but that
commit's own `tools/install_mapupd.py`, in a file only root can change):

    sha256sum /etc/nginx/sites-enabled/play.proto.bar.conf          # the predecessor the installer checks
    sudo cp <checkout>/tools/install_mapupd.py /root/ && sudo chmod 700 /root/install_mapupd.py
    sudo python3 -I /root/install_mapupd.py --source <checkout> --commit <sha> --expected-nginx-sha256 <hash>          # dry run
    sudo python3 -I /root/install_mapupd.py --source <checkout> --commit <sha> --expected-nginx-sha256 <hash> --apply

It is `tools/install_tasupd.py` with the names changed: git and the import check run as proto, the files are the
commit's git objects, the release goes to `/opt/ftesurf-mapupd/<commit>/` (root's alone), the store
`/srv/nvme/ftesurf-ops/mapupd-state` (proto, 0700, chowned through its fd), the unit `ftesurf-mapupd.service`
(gunicorn 127.0.0.1:8096, 1 worker / 4 threads, ProtectSystem=strict, writes only the store, the library, the two zone
dirs, the site media and mapwatch's data dir), `/etc/nginx/snippets/ftesurf-mapupd.conf` included beside surfd's and
`/etc/nginx/conf.d/ftesurf-mapupd-zones.conf` (connection limits). nginx: `POST /mapup/api/part` up to 1100m with no
request buffering (a 1 GB body must not spool to the 27 GB root filesystem), two connections an address, four in all;
every other `/mapup/api/` route 8k; `/ftesurf/media/uploads/<map>[-thumb].jpg` serves the pictures. Both probes read
`POST /mapup/api/health` (the service reading its store and surfd's accounts itself). A failure puts nginx and the unit
back. `--upgrade-from <installed commit>` moves it to a new commit and keeps the old release as the way back.

## Roles (as proto)

Every account is refused until granted. The zone admins (Proto, Markbeaton54 on 23 Nov) in one step, ids never printed:

    python3 /opt/ftesurf-mapupd/<commit>/mapupd.py --store /srv/nvme/ftesurf-ops/mapupd-state grant-zone-admins
    ... grant --identity-file F | revoke --identity-file F    (F: one SteamID64, kept private; revoke closes open uploads)
    ... roles   (a count)   ... list   (published uploads)

## What an upload does

1. `challenge {manifest}` -> a code (time, salt, MAC; 10 min). The game asks once the manifest stops changing.
2. `begin` = the manifest + `nonce/pub/sig`: the signature is the menu's `friends_sign(nonce, "mapupload",
   sha256(manifest))` (the FTESURF-FRIENDS statement, op mapupload; the engine signs it off a lobby, or on one only
   under a device's press, and the menu offers it only in the main menu, a game it hosts, or a lobby the directory
   lists). The key must be linked to an unbanned account holding the role; the name must be new (`surf_`/`bhop_`):
   no BSP in the library, no row in the list or table; 20 GB must stay free; 10 maps / 8 GB an account a day. A retry
   replaces the account's earlier attempt at that name. P1799: zones are optional for every mode, and zone files
   already on the server do not hold a name -- zone files are all zone_edit's Publish (zonepub) writes, so a name
   published before its map is free. The answer says when any directory a lobby reads (MAPUPD_ZONECHECK) holds zones
   of that name (`zones`, `note`): which copies an attached file replaces (zonepub's two dirs), which are left, and a
   warning for a `data/maps/zones/local` copy, which lobbies read first (QC_FixFileName) and which would still win.
3. `part` per file: a `FTESURF-MAPUP-PART 1` head, then the bytes (the map gzipped by the game). Size and SHA-256 must
   be the manifest's (inflate bounded by the confirmed size, 4 MB a call); one stream a file. Spool `<store>/spool/`.
4. `finish`: role and ban looked at again; every spooled file hashed again; VBSP 17-21 or 25 with all 64 lumps inside
   the file; zones through `zonepub.validate`; the picture through Pillow (PNG/JPEG/TGA only, 160x90 to 40 MP; a 16:9
   320x180 thumb and a <= 1920x1080 card), rendered in memory, and the BSP staged as `.mapupd.<name>.bsp.part`: all
   that can fail without touching a shared file, first, so a refused picture never changes a zone file. Then under
   zonepub's own lock (`publish.lock` beside its store, as zonepub_publish.locked takes it; opened read-only, since
   the unit cannot write that directory and flock needs no write access; 30 s, then "try again") and the content
   lease: an earlier attempt's record with no uploads row (it crashed with its zones live) is undone first, unless
   zonepub's history (its store beside the lock, read-only) has a publication of that map that wrote or confirmed
   its files (live, noop, rollback and their partial kinds) queued or applied (`at` or `live`) since the record's time
   (taken under the lock): then the files are that publish's (an identical publish is a noop row) and are left; zone
   files already in zonepub's two dirs are copied to `<store>/zones-aside/` (private, never served); the
   `upload_zones` row is written; the zones; the pictures into `ftesurf-site/media/uploads/`; the BSP linked into
   `game/momentum/maps/` last (never over a file); the `uploads` row. If the pictures or the link fail, the old zone
   files are put back byte for byte, the copies and the record dropped (no old file: the new one goes). No zones
   attached: the zone dirs are not touched. Zones in the other lobby dirs are never written.

The map list (`surfd/data/mapwatch/mapdl.txt`, mapwatch's) and the site's map table (`media/mapmeta.txt`) get a row;
a rewrite by their own writers drops it, and the minute tick (`heal`) puts it back for maps still in the library.
Every write is checked with the reader's rules first (`mapmanifest.read_list`; one `# end N` matching the meta rows)
and refused if the file changed while it was read. R2 mirrors the BSP at its next :05/:35 run; until then players
download it from the Pi. Uploaded zones are not in zonepub's history (the zoning page does not list them).

## The store

`mapupd.db`: roles, nonces, sessions, uploads, and (P1799) `upload_zones(map, sha, aside)`: the SHA-256 of the zone
file the upload wrote ('' none), a JSON list, one entry per zone dir it wrote (`dir`; `file`, its copy in
`zones-aside/` of what it replaced there, and that copy's `sha`, both '' for none), and `at`, when. Written before
the first zone write; a row with no `uploads` row is an attempt that crashed (the next finish of that name undoes it) or a remove
left part done (a re-run continues). A table of its own, not columns on `uploads`: `init` is the migration and runs
while the old release still serves (`--upgrade-from`), which inserts 12 values into `uploads`. It is additive:
CREATE ... IF NOT EXISTS, and `at` added (ALTER TABLE, default 0) to a table made by P1799's first commits, where 0
makes any zonepub publication count as later, so zone files are left. The service and `remove` do the same. An
upload from before P1799 has no row. `list` shows how many zone files each upload replaced.

## Taking an upload back (as proto)

    python3 /opt/ftesurf-mapupd/<commit>/mapupd.py --store /srv/nvme/ftesurf-ops/mapupd-state remove --map <name> \
        --maps /srv/nvme/ftesurf-server/game/momentum/maps --zone-dir /srv/nvme/ftesurf-server/game/ftesurf/maps/zones/local \
        --zone-dir /srv/nvme/ftesurf-site/zones --media /srv/nvme/ftesurf-site/media --list /srv/nvme/surfd/data/mapwatch/mapdl.txt

All of it under zonepub's lock, the rows read there too (a finish of the same name cannot slip between the read and
the writes): the BSP to `maps/.old/<name>.removed-<time>.bsp`, the zones (the record updated at once), pictures and
table rows, the uploads row last (the tick heals only maps still in the library). A failed remove can be run again:
each step finds its own work done. Zones (P1799): only the ones the upload placed, per recorded dir. A file still
the upload's (its SHA-256) is copied to `zones-aside/` and either replaced by what the upload displaced (checked
against its SHA-256) or taken out; one already back as it was before the upload counts as done. A dir not given with
`--zone-dir`, a file gone or changed since, a missing copy, or a read or write that fails is left and stays in
`upload_zones` (the output names the copy of what it replaced), and the command exits 1. All are left when zonepub
has published the map since the upload, or its history cannot be read; so is everything for an upload that brought
no zones or one from before P1799 (who brought which files is not recorded). It prints what it did per file. Old zones an upload replaced stay in
`zones-aside/` until a remove puts them back; there is no other command. A lobby on the map keeps it until its next
change; R2's copy goes with r2mirror's next run.

## Limits (BACKLOG)

- zonepub prunes its history (KEEP_PER_MAP 32, KEEP_TOTAL 1024): a publication pruned before a reconcile or remove
  reads is not seen, and an identical publish since could then be taken back. Falsifier: a crashed attempt, the same
  zones published with zone_edit, 33 more publishes of that map, then a retry without zones.
- A record left by remove (a dir not handled, a file changed since, zonepub's history unreadable) stays until a re-run
  can act on it; one whose file was changed by a later publish can only be cleared by hand (DELETE FROM upload_zones).
- A crashed attempt's record that reconcile kept (zone_edit published since) is replaced by the next attempt's own;
  the copies it named stay in zones-aside/ and are logged, not recorded.
