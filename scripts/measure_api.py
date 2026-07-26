"""Mät Landvex API mot budgetarna – riktiga anrop, inga uppskattningar.

    python3 -m scripts.measure_api                     # startar egen server
    python3 -m scripts.measure_api --base http://127.0.0.1:8000 --runs 30
    python3 -m scripts.measure_api --out /tmp/m.json

Kör varje budgetad endpoint N gånger mot den verkliga motorn och skriver
en mätfil som `scripts/perf_budget.py` läser. Mäter från att anropet
skickas till att svaret är läst – samma punkt varje gång.

Uppvärmningsanropen räknas inte: första anropet betalar importer och
cache-uppbyggnad, och att blanda in det mäter något annat än det en
användare möter på anrop nummer två.

Lokala anrop går förbi eventuell utgående proxy (urllib respekterar inte
NO_PROXY som curl gör), annars mäts proxyn i stället för motorn.

Rent stdlib.
"""
from __future__ import annotations

import json
import os
import tempfile
import subprocess
import sys
import time
import urllib.request

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# id → (metod, path, body). Speglar docs/landvex-budgets.json.
CALLS: dict[str, tuple] = {
    "catalog": ("GET", "/v1/catalog", None),
    "ask": ("POST", "/v1/ask",
            {"question": "What are the biggest opportunities in Örebro?"}),
    "assess_city": ("POST", "/v1/indices/assess",
                    {"kommun_kod": "1880", "market": "se"}),
    "report": ("POST", "/v1/report",
               {"kommun_kod": "1880", "vertical": "solceller",
                "market": "se"}),
    "forecast": ("POST", "/v1/workforce/forecast",
                 {"kommun_kod": "1880", "target_year": 2035, "market": "se"}),
    "saturation": ("POST", "/v1/saturation",
                   {"vertical": "elektriker", "region": "Tyresö",
                    "market": "se"}),
    "merit": ("POST", "/v1/merit", {"market": "se", "top_n": 6}),
    "livability": ("POST", "/v1/livability",
                   {"occupation": "sjukskoterska", "household": "single_parent",
                    "markets": ["se", "de"], "top_n": 6, "per_market": 8}),
    "monitors_evaluate": ("POST", "/v1/monitors/evaluate",
                          {"monitor": {"id": "m", "metric": "debt_gdp",
                                       "scope": "SE", "rule": "threshold",
                                       "owner": "o",
                                       "params": {"level": 60,
                                                  "direction": "above"}},
                           "series": [55, 58, 62]}),
}


def once(base: str, method: str, path: str, body) -> tuple[float, int]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with _OPENER.open(req, timeout=120) as r:
            r.read()
            code = r.status
    except Exception as e:  # noqa: BLE001
        return -1.0, getattr(e, "code", 0)
    return (time.perf_counter() - t0) * 1000.0, code


def runs_needed(cid: str, floor: int, budgets: dict) -> int:
    """Kör så många gånger som GRINDEN kräver för sin percentil.

    Annars mäter man 12 gånger, får "otillräckligt underlag" och frestas
    sänka kravet i stället för att köra klart. Mätaren ska känna till
    grindens regel, inte tvärtom.
    """
    from scripts.perf_budget import min_samples_for
    for b in budgets.get("budgets", []):
        if b["id"] == cid:
            return max(floor, min_samples_for(float(b["percentile"])))
    return floor


def measure(base: str, runs: int, warmup: int = 2,
            budgets: dict | None = None) -> dict:
    budgets = budgets or {}
    out = {}
    for cid, (m, path, body) in CALLS.items():
        runs = runs_needed(cid, runs, budgets)
        for _ in range(warmup):          # importer/cache – räknas inte
            once(base, m, path, body)
        vals = []
        for _ in range(runs):
            ms, code = once(base, m, path, body)
            if ms < 0 or code >= 400:
                print(f"  ! {cid}: call failed (HTTP {code}) — recording "
                      f"nothing rather than a fake timing")
                vals = []
                break
            vals.append(round(ms, 3))
        if vals:
            out[cid] = vals
            vals_sorted = sorted(vals)
            p95 = vals_sorted[min(len(vals) - 1, int(len(vals) * 0.95))]
            print(f"  {cid:20s} n={len(vals):3d}  median "
                  f"{vals_sorted[len(vals)//2]:8.1f} ms   p95 {p95:8.1f} ms")
    return out


def _serve(port: int, live: bool = False):
    """Starta servern att mäta mot.

    `live=False` (default) mäter REN MOTORTID: inga externa källor alls.
    Det är rätt för att jämföra kod mot kod — men det är INTE den
    konfiguration en användare kör, och skillnaden har kostat en gång
    redan. /v1/saturation låg på 19 000 ms mot en budget på 1 500 därför
    att den gjorde ett blockerande HTTPS-anrop per jämförelsekommun. Den
    här mätningen såg 16 ms, eftersom LANDVEX_LIVE=0 hoppar över hela den
    vägen. Budgeten fanns, verktyget fanns, och ingendera kunde se felet.

    `--live` mäter med källkedjan påslagen, alltså vägen produktionen tar.
    """
    env = dict(os.environ, LANDVEX_DB="off", LANDVEX_HOST="127.0.0.1",
               LANDVEX_PORT=str(port), LANDVEX_LIVE="1" if live else "0")
    p = subprocess.Popen([sys.executable, "-m", "api.dev_server"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        time.sleep(0.25)
        ms, code = once(base, "GET", "/health", None)
        if code == 200:
            return p, base
    p.terminate()
    raise SystemExit("server did not start")


def main(argv: list[str]) -> int:
    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    # --live mäter källkedjan påslagen, alltså vägen produktionen tar.
    live = "--live" in argv
    runs = int(opt("--runs", "20"))
    out_path = opt("--out", os.path.join(tempfile.gettempdir(),
                                    "landvex-measurements.json"))
    base = opt("--base", "")
    proc = None
    if not base:
        proc, base = _serve(int(opt("--port", "8288")), live=live)
    bpath = opt("--budgets", os.path.join("docs", "landvex-budgets.json"))
    try:
        with open(bpath, encoding="utf-8") as fh:
            budgets = json.load(fh)
    except Exception:  # noqa: BLE001
        budgets = {}
    läge = "live source chain" if live else "mock only — engine time"
    print(f"measuring {base} · at least {runs} runs per endpoint, more where "
          f"the percentile demands it\n(sources: {läge})\n")
    if not live:
        print("NOTE: LANDVEX_LIVE=0, so the live-source path is NOT measured "
              "here.\n      Endpoints that call an external register or API "
              "are timed\n      without that call. Run with --live to cover "
              "it. Unmeasured is\n      not the same as fast.\n")
    try:
        data = measure(base, runs, budgets=budgets)
    finally:
        if proc is not None:
            proc.terminate()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"\nwrote {out_path} ({len(data)} of {len(CALLS)} endpoints)")
    print("check it with:  python3 -m scripts.perf_budget "
          f"{out_path} --budgets docs/landvex-budgets.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
