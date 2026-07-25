"""SVK / ENTSO-E pre-flight probe — run in a NETWORKED environment.

    LANDVEX_SVK_URL=https://www.svk.se/services/controlroom python3 -m scripts.svk_probe

Fetches the production mix and reports the derived stability_score and
balance_mw so the endpoint shape can be verified before trusting it.
Read-only. Exit 0 if a mix was returned, 1 otherwise.
"""
from __future__ import annotations

import sys

from engine.datasources.svk import SvkClient


def main() -> int:
    client = SvkClient()
    print(f"SVK probe → {client.base_url or '(LANDVEX_SVK_URL not set)'}"
          f"  (EIC {client.status()['eic']})\n")
    if not client.connected:
        print("RESULT: not connected — set LANDVEX_SVK_URL")
        return 1
    try:
        out = client.production_mix()
    except Exception as e:  # noqa: BLE001 - diagnostics
        print(f"  ✗ {type(e).__name__}: {str(e)[:60]}")
        out = None
    if out and out.get("mix"):
        print(f"  ✓ mix: {out['mix']}")
        print(f"    production_mw={out.get('production_mw')} "
              f"stability={out.get('stability_score')} "
              f"balance={out.get('balance_mw')}")
        print("\nRESULT: SVK reachable.")
        return 0
    print("\nRESULT: no production mix returned. Check the endpoint path.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
