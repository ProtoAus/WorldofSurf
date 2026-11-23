# P1744 booster-world model

Exhaustive search over one or two players' Enable/Disable/Toggle sequences on one booster (own rows, other entities',
the world's; restarts, fallback, departures), comparing each player's gate and P1185 bank owner with the old global
switch and with their own-world projection. Written by P1744's reviewers (rounds 4-7); `model.py` (`MARK=head`) is
the design as landed. Run from this folder, e.g. `python3 model.py` (see its header for the environment switches).
Planted bugs (copies not stepped, a drop rule ignoring the owner) produce clean-path hits, so a clean run means something.
