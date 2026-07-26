"""Ninety seconds against the real API — including one refusal.

    python3 -m scripts.demo90                 # starts its own server
    python3 -m scripts.demo90 --base http://localhost:8000
    python3 -m scripts.demo90 --pace          # real pauses, for presenting
    python3 -m scripts.demo90 --json          # machine-readable, for CI

A system without a demo is not finished; it is merely true. This one runs
against the RUNNING API — no scripted text, no canned answers. Every beat
prints the endpoint it called and how long that call took, so anyone
watching can reproduce it.

The dramaturgy is chosen, not incidental. Beat 4 is the only reason to
watch: there the platform refuses to answer. Every comparable tool
returns a confident number at that point. A refusal is the one thing a
competitor cannot show, so it belongs in the middle of the demo rather
than in a footnote at the end.

Three rules this script holds itself to, being the demo for a platform
about not overstating things:

  * **No invented timings.** The first version printed 0:00, 0:15, 0:35
    as though they were elapsed time. It ran in twenty seconds. Every
    time shown here is measured.
  * **Ninety seconds is a claim, not a slogan.** The run is timed against
    BUDGET_S and fails if it overruns.
  * **It can fail itself.** Each beat checks the assertion the narration
    just made, and the exit code is 1 if any of them did not hold. A demo
    that always exits 0 is a recording.

Colour is emitted only to a terminal. Piped to a file you get plain text
instead of escape codes.
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
# Localhost must never go through the egress proxy.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

BUDGET_S = 90.0          # the claim in the name, enforced in run()
_W = 76

_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    """Colour for a terminal; a pipe or a file gets plain text."""
    return f"\033[{code}m{text}\033[0m" if _TTY else text


class Call:
    """One API call, and what it cost."""

    __slots__ = ("path", "ms", "data")

    def __init__(self, path: str, ms: float, data: dict):
        self.path, self.ms, self.data = path, ms, data

    def get(self, key, default=None):
        return self.data.get(key, default)


def _call(base: str, path: str, body: dict | None = None) -> Call:
    url = base.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    t0 = time.perf_counter()
    try:
        with _OPENER.open(req, timeout=30) as r:
            payload = json.loads(r.read())
    except urllib.error.HTTPError as e:
        payload = {"_http_status": e.code, **json.loads(e.read() or b"{}")}
    ms = (time.perf_counter() - t0) * 1000.0
    return Call(path, ms,
                payload if isinstance(payload, dict) else {"_list": payload})


def _serve(port: int) -> tuple[subprocess.Popen, str]:
    env = {**os.environ, "LANDVEX_DB": "off", "LANDVEX_PORT": str(port),
           "LANDVEX_HOST": "127.0.0.1", "LANDVEX_AUDIT_LOG": "off",
           "PYTHONPATH": _ROOT}
    proc = subprocess.Popen([sys.executable, "-m", "api.dev_server"],
                            cwd=_ROOT, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(200):
        try:
            _call(base, "/health")
            return proc, base
        except OSError:
            time.sleep(0.1)
    proc.terminate()
    raise SystemExit("dev server did not start")


class Demo:
    """Narrator and scorekeeper. Every beat records whether it held."""

    def __init__(self, pace: bool):
        self.t0 = time.perf_counter()
        self.pace = pace
        self.beats: list[dict] = []
        self._n = 0

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.t0

    def beat(self, title: str, call: Call) -> None:
        self._n += 1
        print()
        print(_c("1", f"{self._n}. {title}"))
        print(_c("2", f"   {self.elapsed:5.1f}s · {call.path} "
                      f"· {call.ms:.0f} ms"))

    def says(self, text: str, indent: str = "   ") -> None:
        """Wrap to the column width, honouring the indent."""
        width = max(20, _W - len(indent))
        row = ""
        for word in text.split():
            if len(row) + len(word) + 1 > width:
                print(indent + row)
                row = word
            else:
                row = f"{row} {word}".strip()
        if row:
            print(indent + row)

    def shows(self, text: str) -> None:
        print(f"     {text}")

    def holds(self, claim: str, ok: bool) -> None:
        """Record whether the beat did what the narration just said."""
        self.beats.append({"claim": claim, "held": bool(ok),
                           "at_s": round(self.elapsed, 2)})
        if not ok:
            print(_c("1;31", f"     ✗ {claim}"))

    def pause(self, seconds: float) -> None:
        if self.pace:
            time.sleep(seconds)


def run(base: str, pace: bool = False) -> tuple[int, dict]:
    d = Demo(pace)
    print(_c("1", "═" * _W))
    print(_c("1", "  LANDVEX — a ninety-second look"))
    print(_c("1", "═" * _W))

    # ── 1. What is this? ─────────────────────────────────────────────
    s = _call(base, "/v1/surface")
    d.beat("What is this?", s)
    for p in s.get("promises", []):
        d.shows(f"{p['order']}. {p['question_en']}")
    d.says(f"{s.get('engine_count')} engines and {s.get('endpoint_count')} "
           f"endpoints underneath. You are offered four questions.")
    d.holds("the surface offers exactly four promises",
            s.get("promise_count") == 4)
    d.pause(8)

    # ── 2. A question in plain language ──────────────────────────────
    q = "Where is the need for electricians greatest?"
    a = _call(base, "/v1/ask", {"question": q})
    d.beat("Ask it something", a)
    d.shows(_c("3", f'"{q}"'))
    d.says(a.get("svar_en") or "no answer", indent="     ")
    for row in (a.get("rader") or [])[:3]:
        d.shows(f"  · {str(row.get('label_en') or row.get('id')):<26}"
                f"score {row.get('score')}")
    d.says("The market is named in the answer itself, so nobody has to "
           "assume which country the ranking is about.")
    d.holds("the question is answered in prose, with rows",
            bool(a.get("svar_en")) and bool(a.get("rader")))
    d.pause(14)

    # ── 3. The answer carries its own coverage ───────────────────────
    r = _call(base, "/v1/report", {"kommun_kod": "0138", "market": "se",
                                   "vertical": "elektriker"})
    d.beat("The answer shows what it rests on", r)
    d.shows(_c("3", "Electricians in Tyresö, Sweden (municipality 0138)"))
    cov = (r.get("analysis") or {}).get("data_coverage")
    d.shows(_c("1", f"data_coverage: {cov}"))
    if cov == 0.0:
        d.says("Zero. Not one signal in this report comes from a connected "
               "live source, and the report says so on its own front "
               "instead of letting the reader assume otherwise.",
               indent="       ")
    elif cov is not None:
        d.says(f"{cov:.0%} of the signals come from connected sources; the "
               f"rest are labelled mock.", indent="       ")
    d.says("A confidence figure that never drops is a decoration. This one "
           "is allowed to read zero.")
    d.holds("the report states its own data coverage", cov is not None)
    d.pause(16)

    # ── 4. THE REFUSAL — the reason to watch ─────────────────────────
    sat = _call(base, "/v1/saturation", {"vertical": "elektriker",
                                         "region": "0138", "market": "se"})
    d.beat("The question it will not answer", sat)
    d.shows(_c("3", '"How saturated is the market for electricians '
                    'in Tyresö?"'))
    sup = sat.get("supply") or {}
    d.shows(_c("1;33", f"→ establishments: {sup.get('establishments')}   "
                       f"measured: {sup.get('measured')}"))
    d.shows(f"  population {sat.get('population')} · industry code known "
            f"· municipality known")
    d.says(sup.get("basis_en") or "", indent="       ")
    d.says("It has the municipality, the population and the industry code. "
           "It still will not put a number on it. Every comparable tool "
           "returns a confident figure here — that is the difference, and "
           "it belongs in the middle of the demo, not in a footnote.")
    d.holds("saturation refuses rather than inventing a count",
            sup.get("measured") is False
            and sup.get("establishments") is None)
    d.pause(20)

    # ── 5. The decision gets an owner, or it is not a decision ───────
    expected = {"metric": "omsattning", "direction": "increase",
                "target": 12.0}
    bad = _call(base, "/v1/decisions/commit",
                {"decision": "Open a second salon in Örebro",
                 "owners": {}, "expected": expected})
    d.beat("A decision with no owner is refused", bad)
    d.shows(_c("1;33", f"→ {bad.get('error', '')}"))
    good = _call(base, "/v1/decisions/commit",
                 {"decision": "Open a second salon in Örebro",
                  "owners": {"formellt": "A. Lindqvist",
                             "operativt": "M. Ohlsson",
                             "uppfoljning": "Internal audit"},
                  "expected": expected, "kpi_ids": ["omsattning"],
                  "horizon_months": 18})
    d.shows(f"with three named owners → {str(good.get('id'))[:12]}   "
            f"status {good.get('status')}")
    d.says("Refused at the moment the commitment is made — not discovered "
           "by an auditor two years later.")
    d.holds("commitment requires named owners",
            bool(bad.get("error")) and bool(good.get("id")))

    # ── Summary ──────────────────────────────────────────────────────
    total = d.elapsed
    failed = [b for b in d.beats if not b["held"]]
    within = total <= BUDGET_S
    print()
    print("─" * _W)
    print(f"  {len(d.beats) - len(failed)}/{len(d.beats)} beats held · "
          f"{total:.1f}s of a {BUDGET_S:.0f}s budget")
    if failed:
        print(_c("1", f"  {len(failed)} beat(s) did not do what the "
                      f"narration claims:"))
        for b in failed:
            print(f"    · {b['claim']}")
        print(_c("2", "  The demo fails itself rather than misrepresent "
                      "the platform.\n"))
    elif not within:
        print(_c("1", f"  Over the ninety-second budget by "
                      f"{total - BUDGET_S:.1f}s."))
        print(_c("2", "  The name is a claim, so overrunning it is a "
                      "failure, not a note.\n"))
    else:
        print(_c("1", "  Everything above came from the running API."))
        print(_c("2", "  The fourth beat is the product.\n"))

    report = {"beats": d.beats, "elapsed_s": round(total, 2),
              "budget_s": BUDGET_S, "within_budget": within,
              "failed": len(failed), "ok": not failed and within}
    return (0 if report["ok"] else 1), report


def main(argv: list[str]) -> int:
    def opt(name: str, default: str = "") -> str:
        return argv[argv.index(name) + 1] if name in argv else default

    base, proc = opt("--base"), None
    if not base:
        proc, base = _serve(int(opt("--port", "8390")))
    try:
        code, report = run(base, pace="--pace" in argv)
        if "--json" in argv:
            print(json.dumps(report, indent=2))
        return code
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
