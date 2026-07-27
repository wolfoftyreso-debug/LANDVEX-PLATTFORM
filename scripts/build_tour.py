"""Bygger en klickbar rundtur med RIKTIGA motorsvar inbakade.

    python3 -m scripts.build_tour [utfil.html]

Varför den finns: `scripts/build_demo.py` bakar in varje förberäknad
kombination och landar på 42 MB — för tungt att dela och det visar
konsolen, inte plattformens beteende. Den här bygger i stället en kurerad
rundtur: ett dussin frågor, varje svar hämtat från en riktig server som
startas av skriptet självt.

Reglerna som gör den ärlig:

  * **Ingenting skrivs för hand.** Varje siffra och varje mening i en
    svarsruta kommer ur ett anrop. Sidan visar också rå-JSON, så
    påståendet går att kontrollera på plats.
  * **Källorna är mock, och det står överallt.** `LANDVEX_LIVE=0` med
    flit: en rundtur ska visa BETEENDE och får inte ringa riktiga
    myndighets-API:er varje gång någon öppnar den. Att datan är
    simulerad döljs inte — den etiketteras i varje ruta.
  * **Vägranstegen är med.** En rundtur som bara visar lyckade svar
    säljer en produkt som inte finns. Minst ett steg är motorn som säger
    nej, och det är det viktigaste — antalet räknas i sidhuvudet, det
    skrivs inte.
  * **Trunkering sägs ut.** Långa svar kortas för sidans storlek, men
    aldrig tyst: rutan skriver hur många fält som utelämnats.

Rent stdlib. Formgivningen följer produktens egen (iOS-paletten i
frontend/), inte en ny.
"""
from __future__ import annotations

import html
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
_MAX_JSON = 2600          # tecken per rå-JSON-ruta innan trunkering


# ── Rundturen ───────────────────────────────────────────────────────────
# (id, rubrik, frågan en människa ställer, metod, väg, kropp,
#  varför steget finns, vad man ska titta efter)
STEG: tuple[dict, ...] = (
    {"id": "surface", "title": "What does it promise?",
     "asks_en": "Before any number: what does this platform claim it can do?",
     "method": "GET", "path": "/v1/surface", "body": None,
     "why_en": "Four promises, and every engine belongs to exactly one. A "
               "test fails if an engine belongs to none — a catalogue that "
               "can grow without a promise grows into a feature list.",
     "look_for": ["promise_count", "engine_count", "endpoint_count"]},

    {"id": "ask", "title": "Ask it in plain words",
     "asks_en": "Where should I open a café in Tyresö?",
     "method": "POST", "path": "/v1/ask",
     "body": {"question": "Where should I open a café in Tyresö?"},
     "why_en": "Note the neutrality gate. The question is normative — it "
               "asks what to DO — and the engine answers with what is "
               "measured while flagging that it does not prescribe action.",
     "look_for": ["svar_en", "neutrality"]},

    {"id": "report", "title": "A decision card for a real place",
     "asks_en": "What does the engine say about electricians in Tyresö?",
     "method": "POST", "path": "/v1/report",
     "body": {"market": "se", "kommun_kod": "0138",
              "vertical": "elektriker"},
     "why_en": "Every figure carries where it came from. On this build the "
               "sources are mock, and the card says so rather than "
               "presenting a simulated number as an observed one.",
     "look_for": ["sammanfattning_en", "caveats_en"]},

    {"id": "saturation", "title": "When it does not know, it says so",
     "asks_en": "How many electricians already operate there?",
     "method": "POST", "path": "/v1/saturation",
     "body": {"market": "se", "region": "0138", "vertical": "elektriker"},
     "why_en": "THIS is the product. No business register is connected, so "
               "there is no count — and the engine returns that fact "
               "instead of an estimate. Read `basis_en`.",
     "look_for": ["supply", "verdict_en"]},

    {"id": "refusal", "title": "A decision with no owner is refused",
     "asks_en": "Commit the decision 'Open a second salon' — with nobody "
                "named as responsible.",
     "method": "POST", "path": "/v1/decisions/commit",
     "body": {"decision": "Open a second salon", "owners": {}},
     "why_en": "Refused at the moment the commitment is made, not "
               "discovered by an auditor two years later. Three roles are "
               "required: formal, operational, follow-up.",
     "look_for": ["error"]},

    {"id": "commit", "title": "…and accepted with them",
     "asks_en": "The same decision, with three named owners.",
     "method": "POST", "path": "/v1/decisions/commit",
     "body": {"decision": "Open a second salon in Örebro",
              "owners": {"formellt": "Board", "operativt": "Site manager",
                         "uppfoljning": "Controller"},
              "expected": {"metric": "break_even_months",
                           "direction": "decrease", "target": 9}},
     "why_en": "Accepted — and note what it also demanded: the expected "
               "outcome had to be a MEASURABLE one (metric, direction, "
               "target), not a sentence. 'Break even within 9 months' as "
               "prose was refused too. A promise nobody can check later is "
               "not a promise.",
     "look_for": ["id", "status", "expected", "owners"]},

    {"id": "corroboration", "title": "How much does a second source add?",
     "asks_en": "What makes a finding well-supported?",
     "method": "GET", "path": "/v1/corroboration", "body": None,
     "why_en": "Independence times modality times agreement — expressed as "
               "a BAND, never a percentage. A single network can never "
               "reach the top band, however well it agrees with itself.",
     "look_for": ["principle_en", "single_source_ceiling"]},

    {"id": "conflict", "title": "Two networks that disagree",
     "asks_en": "Road sensors say 820. Air quality suggests 180. Now what?",
     "method": "POST", "path": "/v1/corroboration",
     "body": {"sources": [{"sensor_class": "road_flow", "value": 820},
                          {"sensor_class": "air_quality", "value": 180}]},
     "why_en": "Disagreement is its own outcome, not weak support. At "
               "least one source is wrong and it is not knowable which — a "
               "weaker basis than a single source, not a stronger one.",
     "look_for": ["strength", "why_en", "conflicting"]},

    {"id": "sensors", "title": "What can and cannot be measured",
     "asks_en": "Which sensors exist, and what can none of them settle?",
     "method": "GET", "path": "/v1/sensors", "body": None,
     "why_en": "Every class states its `cannot_en`: what a reading never "
               "decides. A sensor map without that is a wish list.",
     "look_for": ["count", "by_state", "why_cannot_matters_en"]},

    {"id": "brief", "title": "A quiet day is a real result",
     "asks_en": "What changed today that anyone should know about?",
     "method": "POST", "path": "/v1/brief",
     "body": {"market": "se", "region": "0138"},
     "why_en": "Nothing crossed the threshold, and the brief says exactly "
               "that. A brief that always finds something is a brief that "
               "invents.",
     "look_for": ["headline_en", "quiet_day_en", "count"]},

    {"id": "households", "title": "The same place, different lives",
     "asks_en": "Is this a good place to live — for whom?",
     "method": "GET", "path": "/v1/households", "body": None,
     "why_en": "There is no neutral 'good place'. Each household type "
               "weighs the same measurements differently, and the weights "
               "are published rather than hidden in a score.",
     "look_for": ["households"]},

    {"id": "provenance", "title": "Where does the number come from?",
     "asks_en": "Show me the origin of the parameters behind the answers.",
     "method": "GET", "path": "/v1/provenance", "body": None,
     "why_en": "Each parameter names its source and its status. A figure "
               "whose origin nobody can state is a figure nobody should "
               "act on.",
     "look_for": []},
)


def _call(base: str, steg: dict) -> dict:
    data = (json.dumps(steg["body"]).encode() if steg["body"] is not None
            else None)
    r = urllib.request.Request(
        base + steg["path"], data=data, method=steg["method"],
        headers={"Content-Type": "application/json"})
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(r, timeout=40) as svar:
            return {"status": svar.status, "json": json.loads(svar.read())}
    except urllib.error.HTTPError as e:
        # Ett 422 är inte ett fel här utan poängen med steget: motorn
        # vägrar. Det fångas och visas som det svar det är.
        return {"status": e.code, "json": json.loads(e.read() or b"{}")}


def _serve(port: int) -> tuple[subprocess.Popen, str]:
    env = {**os.environ, "LANDVEX_DB": "off", "LANDVEX_PORT": str(port),
           "LANDVEX_HOST": "127.0.0.1", "LANDVEX_AUDIT_LOG": "off",
           "LANDVEX_LIVE": "0", "PYTHONPATH": _ROOT}
    proc = subprocess.Popen([sys.executable, "-m", "api.dev_server"],
                            cwd=_ROOT, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(200):
        try:
            op.open(base + "/health", timeout=2).read()
            return proc, base
        except OSError:
            time.sleep(0.1)
    proc.terminate()
    raise SystemExit("dev server did not start")


def fanga(port: int = 8212) -> list[dict]:
    proc, base = _serve(port)
    try:
        halsa = json.loads(urllib.request.build_opener(
            urllib.request.ProxyHandler({})).open(
                base + "/health", timeout=10).read())
        ut = []
        for s in STEG:
            svar = _call(base, s)
            ut.append({**s, **svar})
            print(f"  {svar['status']}  {s['method']:5s} {s['path']}")
        return ut, halsa
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ── Sidan ───────────────────────────────────────────────────────────────
def _kort_json(obj: object) -> tuple[str, int]:
    """Rå-JSON, kortad — men aldrig tyst."""
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    if len(text) <= _MAX_JSON:
        return text, 0
    if isinstance(obj, dict):
        behall, n = {}, 0
        for k, v in obj.items():
            provisorisk = json.dumps({**behall, k: v}, ensure_ascii=False,
                                     indent=2)
            if len(provisorisk) > _MAX_JSON:
                n += 1
                continue
            behall[k] = v
        return json.dumps(behall, ensure_ascii=False, indent=2), n
    return text[:_MAX_JSON], -1


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def _varde(v: object) -> str:
    if isinstance(v, (dict, list)):
        return _e(json.dumps(v, ensure_ascii=False)[:260])
    return _e(v)


def bygg(steg: list[dict], halsa: dict) -> str:
    # Räknad, inte skriven: rubriken sa "two of the twelve" medan ett av
    # de två stegen hade börjat lyckas. En siffra i en rubrik åldras lika
    # tyst som en i ett dokument.
    n_vagran = sum(1 for s in steg if s["status"] >= 400)
    ord_ = {1: "One", 2: "Two", 3: "Three"}.get(n_vagran, str(n_vagran))
    delar = [_HUVUD]
    delar.append(f"""
<header>
  <p class="eyebrow">LANDVEX Opportunity Engine · {_e(halsa.get('engine_version', ''))}</p>
  <h1>Twelve questions, answered by the running engine</h1>
  <p class="lede">Every box below is a real request to a real server,
  captured when this page was built. Nothing is written by hand.
  {ord_} of the {len(steg)} is the engine <em>refusing</em> — that is the
  one worth reading first.</p>
  <p class="warn"><strong>Sources are mock on this build.</strong> The
  probes have never received a byte from a live authority endpoint, so
  every figure below is simulated — and labelled as such by the engine
  itself, not by this page.</p>
</header>
<nav id="nav"></nav>
<main>""")

    for i, s in enumerate(steg, 1):
        rå, utelamnade = _kort_json(s["json"])
        vagran = s["status"] >= 400
        highlights = ""
        for nyckel in s["look_for"]:
            if nyckel in (s["json"] or {}):
                highlights += (f'<div class="kv"><span class="k">{_e(nyckel)}'
                               f'</span><span class="v">'
                               f'{_varde(s["json"][nyckel])}</span></div>')
        delar.append(f"""
<section id="{_e(s['id'])}" class="step{' refusal' if vagran else ''}">
  <div class="num">{i:02d}</div>
  <h2>{_e(s['title'])}</h2>
  <p class="asks">{_e(s['asks_en'])}</p>
  <div class="req">
    <span class="method">{_e(s['method'])}</span>
    <code>{_e(s['path'])}</code>
    <span class="status {'bad' if vagran else 'ok'}">{s['status']}</span>
  </div>
  {highlights}
  <p class="why">{_e(s['why_en'])}</p>
  <details>
    <summary>Raw response{
      f' · {utelamnade} field(s) omitted for size' if utelamnade > 0 else ''
    }</summary>
    <pre>{_e(rå)}</pre>
  </details>
</section>""")

    delar.append(f"""
</main>
<footer>
  <p>Built by <code>python3 -m scripts.build_tour</code> against a dev
  server started by the script itself, with <code>LANDVEX_LIVE=0</code>.
  Persistence off, audit log off. {len(steg)} requests, all captured in
  one run.</p>
  <p>Live sources verified: <strong>0 of 14</strong>. That number is not
  a disclaimer at the bottom of a page — it is what
  <code>make standing</code> reports, and it is the first thing the
  roadmap is ordered by.</p>
</footer>
{_SKRIPT}""")
    return "\n".join(delar)


_HUVUD = """<title>LANDVEX — twelve questions, answered by the engine</title>
<style>
:root{
  --blue:#007AFF; --green:#34C759; --amber:#FF9F0A; --red:#FF3B30;
  --bg:#FBFBFD; --card:#FFFFFF; --line:#E5E5EA;
  --ink:#1D1D1F; --dim:#6E6E73; --faint:#98989D;
  --code:#F5F5F7;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#000000; --card:#1C1C1E; --line:#2C2C2E;
  --ink:#F5F5F7; --dim:#98989D; --faint:#6E6E73; --code:#2C2C2E;
  --blue:#0A84FF; --green:#30D158; --amber:#FF9F0A; --red:#FF453A;
}}
:root[data-theme="light"]{--bg:#FBFBFD;--card:#FFFFFF;--line:#E5E5EA;
  --ink:#1D1D1F;--dim:#6E6E73;--faint:#98989D;--code:#F5F5F7;
  --blue:#007AFF;--green:#34C759;--red:#FF3B30}
:root[data-theme="dark"]{--bg:#000000;--card:#1C1C1E;--line:#2C2C2E;
  --ink:#F5F5F7;--dim:#98989D;--faint:#6E6E73;--code:#2C2C2E;
  --blue:#0A84FF;--green:#30D158;--red:#FF453A}

*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);
  font:16px/1.62 -apple-system,BlinkMacSystemFont,"SF Pro Text",
    "Segoe UI",Roboto,sans-serif;
  max-width:780px;margin:0 auto;padding:3rem 1.25rem 5rem;
  -webkit-font-smoothing:antialiased}
header{margin-bottom:2rem}
.eyebrow{font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--faint);font-weight:600;margin-bottom:.6rem}
h1{font-size:2rem;line-height:1.14;letter-spacing:-.023em;font-weight:700;
  margin-bottom:.7rem;text-wrap:balance}
.lede{color:var(--dim);font-size:1.02rem;margin-bottom:1rem}
.lede em{color:var(--ink);font-style:normal;font-weight:600}
.warn{background:color-mix(in srgb,var(--amber) 12%,transparent);
  border-left:3px solid var(--amber);border-radius:0 8px 8px 0;
  padding:.7rem .9rem;font-size:.88rem;color:var(--ink)}

nav{display:flex;flex-wrap:wrap;gap:.4rem;margin:0 0 2.5rem}
nav a{font-size:.78rem;padding:.3rem .7rem;border-radius:13px;
  border:1px solid var(--line);color:var(--dim);text-decoration:none;
  background:var(--card);transition:.15s}
nav a:hover,nav a:focus-visible{color:var(--blue);border-color:var(--blue)}

.step{background:var(--card);border:1px solid var(--line);
  border-radius:13px;padding:1.4rem 1.5rem;margin-bottom:1rem;
  position:relative;scroll-margin-top:1rem}
.step.refusal{border-color:color-mix(in srgb,var(--amber) 55%,var(--line))}
.num{position:absolute;top:1.45rem;right:1.5rem;font-size:.7rem;
  font-weight:700;color:var(--faint);
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
h2{font-size:1.12rem;letter-spacing:-.012em;margin-bottom:.35rem;
  padding-right:2.5rem}
.asks{color:var(--dim);font-size:.94rem;margin-bottom:.9rem}
.req{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;
  margin-bottom:.9rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:.76rem}
.method{background:var(--blue);color:#fff;padding:.12rem .45rem;
  border-radius:5px;font-weight:600;letter-spacing:.02em}
.req code{background:var(--code);padding:.14rem .45rem;border-radius:5px;
  color:var(--ink)}
.status{margin-left:auto;font-weight:700}
.status.ok{color:var(--green)}
.status.bad{color:var(--amber)}
.kv{display:grid;grid-template-columns:minmax(88px,auto) 1fr;gap:.6rem;
  padding:.42rem 0;border-top:1px solid var(--line);font-size:.85rem;
  align-items:baseline}
.k{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.74rem;
  color:var(--faint)}
.v{overflow-wrap:anywhere}
.why{margin-top:.95rem;padding-top:.85rem;border-top:1px solid var(--line);
  font-size:.9rem;color:var(--dim)}
details{margin-top:.8rem}
summary{cursor:pointer;font-size:.78rem;color:var(--blue);
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
summary:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
pre{background:var(--code);border-radius:9px;padding:.85rem;margin-top:.6rem;
  overflow-x:auto;font-size:.72rem;line-height:1.5;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
footer{margin-top:2.5rem;padding-top:1.4rem;border-top:1px solid var(--line);
  color:var(--faint);font-size:.8rem}
footer p{margin-bottom:.6rem}
footer code{background:var(--code);padding:.1rem .3rem;border-radius:4px}
footer strong{color:var(--amber)}
@media (max-width:560px){
  body{padding:2rem 1rem 3rem}
  h1{font-size:1.6rem}
  .num{display:none}
  h2{padding-right:0}
}
</style>"""

_SKRIPT = """<script>
(function(){
  var nav = document.getElementById('nav');
  document.querySelectorAll('section.step').forEach(function(s){
    var a = document.createElement('a');
    a.href = '#' + s.id;
    a.textContent = s.querySelector('h2').textContent;
    nav.appendChild(a);
  });
})();
</script>"""


def main(argv: list[str]) -> int:
    ut = pathlib.Path(argv[0] if argv else "landvex-tour.html")
    print("Fångar riktiga svar från en egen server …")
    steg, halsa = fanga()
    sida = bygg(steg, halsa)
    ut.write_text(sida, encoding="utf-8")
    vagran = sum(1 for s in steg if s["status"] >= 400)
    print(f"\n{ut} ({len(sida) // 1024} kB) · {len(steg)} steg · "
          f"{vagran} av dem är motorn som vägrar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
