"""Live-prob mot de riktiga företagsregistren.

    python3 -m scripts.register_probe se 0138 elektriker
    python3 -m scripts.register_probe us 06037 elektriker
    python3 -m scripts.register_probe de DE300 elektriker
    python3 -m scripts.register_probe all            # alla providers

Kräver utgående nätverk. Kör den i en miljö där api.scb.se,
api.census.gov och ec.europa.eu är nåbara – då, och först då, är
tabellsökvägarna bekräftade. Proben säger rakt ut om den inte kom fram.
"""
from __future__ import annotations

import sys
import traceback

from engine.datasources.register_apis import (PROVIDER_FOR, PXWEB_TABLES,
                                              provider_for, providers_status)
from engine.registers import REGISTERS, industry_code

SAMPLES = [
    ("se", "0138", "elektriker", "Tyresö"),
    ("no", "0301", "elektriker", "Oslo"),
    ("dk", "101", "elektriker", "København"),
    ("fi", "091", "elektriker", "Helsinki"),
    ("us", "06037", "elektriker", "Los Angeles County"),
    ("de", "DE300", "elektriker", "Berlin (NUTS)"),
    ("fr", "FR101", "elektriker", "Paris (NUTS)"),
]


def probe(country: str, region: str, trade: str, label: str = "") -> bool:
    code = industry_code(trade, country)
    reg = REGISTERS.get(country, {})
    print(f"\n── {country.upper()} {label or region} "
          f"({reg.get('name', 'unknown register')})")
    if code is None:
        print("   ✗ no industry code mapped for this trade/country")
        return False
    print(f"   provider : {PROVIDER_FOR.get(country, 'generic')}")
    print(f"   code     : {code['code']} ({code['scheme']})")
    if country in PXWEB_TABLES:
        print(f"   table    : {PXWEB_TABLES[country]['table']}")
    p = provider_for(country)
    try:
        got = p.count(country, region, code["code"])
    except Exception as e:  # noqa: BLE001
        print(f"   ✗ transport error: {type(e).__name__}: {e}")
        return False
    if got is None:
        print("   ✗ no count returned — endpoint unreachable, path wrong, "
              "or the response shape differs. Nothing was invented.")
        return False
    print(f"   ✓ {got['count']} establishments "
          f"({got.get('year') or 'year n/a'}) — {got['source']}")
    return True


def main(argv: list[str]) -> int:
    if len(argv) >= 4:
        ok = probe(argv[1], argv[2], argv[3])
        return 0 if ok else 1
    if len(argv) == 2 and argv[1] == "all":
        st = providers_status()
        print("Providers built:")
        for pr in st["providers"]:
            print(f"  {pr['id']:12s} {', '.join(pr['countries'])[:44]:46s} "
                  f"{pr['protocol']}")
        results = [probe(c, r, t, lbl) for c, r, t, lbl in SAMPLES]
        n = sum(1 for r in results if r)
        print(f"\n{n}/{len(results)} registers answered.")
        if n == 0:
            print("None answered. If this environment blocks outbound "
                  "network, that is the expected result here — run it where "
                  "the network is open before trusting any table path.")
        return 0 if n else 2
    print(__doc__)
    return 64


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(1)
