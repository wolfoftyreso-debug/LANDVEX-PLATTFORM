"""Nittio sekunder. En fråga in, ett svar ut — och en vägran.

    python3 -m scripts.demo90                  # startar servern själv
    python3 -m scripts.demo90 --base http://localhost:8000

Ett system utan demo är inte färdigt, det är bara sant. Den här kör mot
det RIKTIGA API:t — ingen skriptad text, inga påhittade svar. Varje steg
skriver ut vilken endpoint det anropade, så att den som tittar kan göra
om det själv.

Dramaturgin är vald, inte slumpad. Steg 4 är den enda anledningen att
titta: där vägrar plattformen svara. Varje jämförbart verktyg producerar
en självsäker siffra i det läget. Att se en vägran är det enda en
konkurrent inte kan visa upp, och därför är det demons mitt — inte dess
brasklapp på slutet.

Avslutar med 0 om alla fem stegen betedde sig som utlovat, annars 1. En
demo som inte kan fälla sig själv är en inspelning.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Localhost ska aldrig gå via utgångsproxyn.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _call(base: str, path: str, body: dict | None = None) -> dict:
    url = base.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    try:
        with _OPENER.open(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_http_status": e.code, **json.loads(e.read() or b"{}")}


def _serve(port: int) -> tuple[subprocess.Popen, str]:
    env = {**os.environ, "LANDVEX_DB": "off", "LANDVEX_PORT": str(port),
           "LANDVEX_HOST": "127.0.0.1", "LANDVEX_AUDIT_LOG": "off",
           "PYTHONPATH": _ROOT}
    proc = subprocess.Popen([sys.executable, "-m", "api.dev_server"],
                            cwd=_ROOT, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            _call(base, "/health")
            return proc, base
        except OSError:
            time.sleep(0.1)
    raise SystemExit("dev server did not start")


_W = 74


def _beat(n: int, seconds: str, title: str, endpoint: str) -> None:
    print(f"\n\033[1m{n}. {title}\033[0m")
    print(f"   \033[2m{seconds:>7s} · {endpoint}\033[0m")


def _line(text: str, indent: str = "   ") -> None:
    words, row = text.split(), ""
    for w in words:
        if len(row) + len(w) + 1 > _W:
            print(indent + row)
            row = w
        else:
            row = f"{row} {w}".strip()
    if row:
        print(indent + row)


def run(base: str) -> int:
    ok = []
    print("\033[1m" + "═" * _W)
    print("  LANDVEX — nittio sekunder")
    print("═" * _W + "\033[0m")

    # ── 1. Vad är det här? ───────────────────────────────────────────
    _beat(1, "0:00", "Vad är det här?", "GET /v1/surface")
    s = _call(base, "/v1/surface")
    for p in s["promises"]:
        print(f"     {p['order']}. {p['question_en']}")
    _line(f"{s['engine_count']} engines and {s['endpoint_count']} endpoints "
          f"underneath. You are offered four questions.")
    ok.append(s["promise_count"] == 4)

    # ── 2. En fråga på vanlig svenska ────────────────────────────────
    _beat(2, "0:15", "Ställ en fråga", "POST /v1/ask")
    q = "Var är behovet av elektriker störst?"
    print(f"     \033[3m\"{q}\"\033[0m")
    a = _call(base, "/v1/ask", {"question": q})
    _line(a.get("svar_en", ""))
    for row in (a.get("rader") or [])[:3]:
        print(f"       · {row.get('label_en', row.get('id'))}  "
              f"score {row.get('score')}")
    for c in (a.get("caveats_en") or [])[:1]:
        _line(f"caveat: {c}", indent="       ")
    ok.append(bool(a.get("svar_en")))

    # ── 3. Svaret bär sin egen täckning ──────────────────────────────
    _beat(3, "0:35", "Svaret visar vad det vilar på", "POST /v1/report")
    print("     \033[3mElektriker i Tyresö (kommun 0138)\033[0m")
    r = _call(base, "/v1/report", {"kommun_kod": "0138", "market": "se",
                                   "vertical": "elektriker"})
    cov = (r.get("analysis") or {}).get("data_coverage")
    print(f"     \033[1mdata_coverage: {cov}\033[0m")
    if cov == 0.0:
        _line("Zero. Not one signal in this report comes from a connected "
              "live source — and the report says so on its own front, "
              "unprompted, instead of letting the reader assume otherwise.",
              indent="       ")
    else:
        _line(f"{cov:.0%} of the signals come from connected sources; the "
              f"rest are labelled mock.", indent="       ")
    for c in (r.get("caveats_en") or [])[:1]:
        _line(c, indent="       ")
    _line("A confidence figure that never drops is a decoration. This one "
          "is allowed to read zero.")
    ok.append(cov is not None)

    # ── 4. VÄGRAN — anledningen att titta ────────────────────────────
    _beat(4, "0:55", "Frågan den vägrar besvara", "POST /v1/saturation")
    print("     \033[3m\"Hur mättad är marknaden för elektriker "
          "i Tyresö?\"\033[0m")
    sat = _call(base, "/v1/saturation", {"vertical": "elektriker",
                                         "region": "0138", "market": "se"})
    sup = sat.get("supply") or {}
    print(f"     \033[1m\033[33m→ establishments: {sup.get('establishments')}"
          f"   measured: {sup.get('measured')}\033[0m")
    _line(sup.get("basis_en") or sat.get("verdict_en") or "", indent="       ")
    _line("It knows the municipality, the population and the industry code. "
          "It still will not put a number on it. Every comparable tool "
          "returns a confident figure here — that is the difference, and "
          "it is the middle of this demo, not a footnote at the end.")
    ok.append(sup.get("measured") is False
              and sup.get("establishments") is None)

    # ── 5. Beslutet får en ägare — eller blir inget beslut ───────────
    _beat(5, "1:15", "Ett beslut utan ägare avvisas",
          "POST /v1/decisions/commit")
    bad = _call(base, "/v1/decisions/commit",
                {"decision": "Öppna en andra salong i Örebro",
                 "owners": {}, "expected": {"metric": "omsattning",
                                            "direction": "increase",
                                            "target": 12.0}})
    print(f"     \033[1m\033[33m→ {bad.get('error', '')}\033[0m")
    good = _call(base, "/v1/decisions/commit",
                 {"decision": "Öppna en andra salong i Örebro",
                  "owners": {"formellt": "A. Lindqvist",
                             "operativt": "M. Ohlsson",
                             "uppfoljning": "Internrevision"},
                  "expected": {"metric": "omsattning",
                               "direction": "increase", "target": 12.0},
                  "kpi_ids": ["omsattning"], "horizon_months": 18})
    print(f"     med tre namngivna ägare → {str(good.get('id'))[:12]}  "
          f"status {good.get('status')}")
    _line("Refused at the point the commitment is made — not discovered by "
          "an auditor two years later.")
    ok.append(bool(bad.get("error")) and bool(good.get("id")))

    print("\n" + "─" * _W)
    if all(ok):
        print("\033[1m  Fem steg, allt levererat av det riktiga API:t.\033[0m")
        print("  \033[2mDet fjärde är produkten.\033[0m\n")
        return 0
    print(f"\033[1m  {ok.count(False)} av {len(ok)} steg gjorde inte vad "
          f"demon påstår.\033[0m")
    print("  \033[2mDemon fäller sig själv hellre än ljuger om "
          "plattformen.\033[0m\n")
    return 1


def main(argv: list[str]) -> int:
    base, proc = "", None
    if "--base" in argv:
        base = argv[argv.index("--base") + 1]
    if not base:
        port = int(argv[argv.index("--port") + 1]) if "--port" in argv \
            else 8390
        proc, base = _serve(port)
    try:
        return run(base)
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
