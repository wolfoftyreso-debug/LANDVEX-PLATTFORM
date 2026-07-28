"""Läs in de öppna källorna en gång, i förgrunden.

    LANDVEX_OPEN_DATA=on python3 -m scripts.harvest             # allt
    LANDVEX_OPEN_DATA=on python3 -m scripts.harvest osm se      # en källa
    LANDVEX_OPEN_DATA=on python3 -m scripts.harvest osm us --limit 5

Det här är vad man kör FÖRST, för att se att det fungerar, innan
schemaläggaren får sköta det (`engine/scheduler.JOB_KINDS["harvest"]`).

Skörden skriver till samma lager som API:t läser, så `LANDVEX_DB` måste
peka på samma fil — annars fylls en databas ingen frågar.

Källor som kräver nyckel slås aldrig på av `LANDVEX_OPEN_DATA`. Att inte
vara påslagen är ett annat tillstånd än att vara nere, och skripten
skriver ut vilket.

Rent stdlib.
"""
from __future__ import annotations

import os
import sys
import time

from engine import harvest
from engine.markets import MARKETS


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    kallor = [args[0]] if args else list(harvest.SOURCES)
    marknader = [args[1]] if len(args) > 1 else list(MARKETS)
    try:
        i = argv.index("--limit")
        limit = int(argv[i + 1])
    except (ValueError, IndexError):
        limit = 0

    okanda = [k for k in kallor if k not in harvest.SOURCES]
    if okanda:
        print(f"no such source: {', '.join(okanda)}. "
              f"Have: {', '.join(harvest.SOURCES)}")
        return 64

    db = os.environ.get("LANDVEX_DB", "landvex.db")
    if db.lower() in ("off", "0", ""):
        print("LANDVEX_DB is off — there is nowhere to store a harvest, "
              "and the request path would still read mock. Nothing done.")
        return 1
    from engine.storage.sqlite import SqliteStore
    store = SqliteStore(db)
    harvest.set_store(store)

    total, t0 = 0, time.monotonic()
    for kalla in kallor:
        url = harvest.url_for(kalla)
        if not url:
            print(f"  ---- {kalla:12s} not switched on "
                  f"(set {harvest.SOURCES[kalla]['env']} or "
                  f"LANDVEX_OPEN_DATA=on)")
            continue
        print(f"  >>>> {kalla:12s} {url}")
        for mid in marknader:
            if mid not in MARKETS:
                continue
            regioner = MARKETS[mid].regions[:limit or None]
            n = 0
            for region in regioner:
                rader = harvest.harvest_region(kalla, region, mid)
                n += harvest.store_rows(rader)
            total += n
            status = "ok" if n else "no rows — host reached? see the probe"
            print(f"       {mid:4s} {len(regioner):4d} region(s) → "
                  f"{n:5d} row(s)  {status}")

    print(f"\n{total} row(s) stored in {db} "
          f"in {time.monotonic() - t0:.1f}s")
    if not total:
        print("\nNothing was stored. That is not a pass: either no source "
              "is switched on, or nothing answered. The request path will "
              "keep serving the labelled mock.")
    store.close()
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
