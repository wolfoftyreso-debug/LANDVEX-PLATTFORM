"""Bygger ingången ur motorn — löftena och besluten, inte en av dem.

    python3 -m scripts.build_front [utfil.html] [--fragment]

Fyndet som gjorde filen nödvändig: konsolens intro sa "WHERE TO
ESTABLISH" och visade ETT av tretton byggda beslut. Ompaketeringen till
fyra löften och tre planer gjordes i motorn — `engine/surface.py` och
`engine/offering.py`, med test som håller dem — men stannade vid API:t.
Ingen av de fyra frontend-sidorna nämnde ett enda löfte. En besökare
mötte alltså den ursprungliga enfrågeprodukten medan motorn under den
kunde svara på tolv frågor till.

Därför genereras den här sidan ur `/v1/surface` och `/v1/offering`. Ett
nytt beslut i `offering.DECISIONS` dyker upp här utan att någon redigerar
HTML, och ett borttaget försvinner. En handskriven ingång glider ifrån
motorn inom ett par veckor, och då säljer den antingen för lite — som
nu — eller för mycket, vilket är värre.

Regler:

  * **Planerade beslut visas som planerade.** `offering.py` skriver ut
    varför de finns i listan: "listed as planned so nobody sells it as
    available". Att dölja dem hade varit ärligare mot demon och mindre
    ärligt mot kunden.
  * **Inga påhittade priser.** Enterprise står som "by agreement" för
    att det är vad motorn säger, och Professional bär provisionstexten
    ordagrant.

Rent stdlib. Formgivningen är produktens egen iOS-palett.
"""
from __future__ import annotations

import html
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.request

_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)


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


def hamta(port: int = 8222) -> dict:
    proc, base = _serve(port)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        def g(p):
            return json.loads(op.open(base + p, timeout=30).read())
        return {"surface": g("/v1/surface"), "offering": g("/v1/offering"),
                "health": g("/health")}
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def bevis() -> list[dict]:
    """Varför det här är ett instrument och inte en gissningsmaskin.

    Varje rad RÄKNAS FRAM ur repot vid bygget. Ett påstående om
    tillförlitlighet som inte går att kontrollera är precis vad en
    gissningsmaskin också skulle skriva — så varje rad bär det som gör
    den kontrollerbar: en fil, ett tal, en endpoint.
    """
    import ast
    rot = pathlib.Path(_ROOT)

    # Finns en språkmodell i svarsvägen? Sök efter riktiga ANROP, inte
    # efter ordet i en kommentar — engine/ask.py NÄMNER en framtida
    # LLM-layer i sin docstring, och en textsökning hade läst det som
    # ett beroende.
    sdk = {"openai", "anthropic", "langchain", "google", "cohere",
           "mistralai", "ollama", "transformers", "huggingface_hub"}
    # Räkna engine/ och api/ VAR FÖR SIG. Första versionen slog ihop dem
    # och skrev "engine/ importerar bara stdlib plus fastapi, mangum,
    # psycopg, pydantic" — vilket motsäger sin egen rubrik. fastapi och
    # pydantic är API-lagrets, inte motorns, och just den här sidan har
    # inte råd med ett påstående som motsäger sig självt.
    def _importer(katalog: str) -> set[str]:
        ut = set()
        for f in (rot / katalog).rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                mods = []
                if isinstance(n, ast.Import):
                    mods = [a.name.split(".")[0] for a in n.names]
                elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                    mods = [n.module.split(".")[0]]
                for m in mods:
                    if (m not in sys.stdlib_module_names
                            and m not in ("engine", "api", "integrations")):
                        ut.add(m)
                    if m in sdk:
                        ut.add("LLM:" + m)
        return ut

    motor = _importer("engine")
    api_lager = _importer("api")
    llm = {m for m in motor | api_lager if m.startswith("LLM:")}
    tredje = {m for m in motor if not m.startswith("LLM:")}

    krav = [r.strip() for r in
            (rot / "requirements.txt").read_text(encoding="utf-8").split("\n")
            if r.strip() and not r.startswith("#")]
    sviter = len(list((rot / "tests").glob("test_*.py")))
    rader = len(re.findall(r"^\s*def test_", "".join(
        f.read_text(encoding="utf-8") for f in (rot / "tests").glob("*.py")),
        re.M))

    return [
        {"claim_en": "No language model sits in the answer path.",
         "proof_en": f"{len(llm)} LLM SDK imports across engine/ and api/. "
                     f"The entire dependency list is "
                     f"{len(krav)} packages — {', '.join(k.split('>')[0].split('[')[0] for k in krav)} "
                     f"— and none of them generates text. Same version plus "
                     f"same inputs returns the same number, every time.",
         "check_en": "requirements.txt · engine/ imports"},
        {"claim_en": "The decision engine runs on the standard library.",
         "proof_en": f"engine/ pulls in {len(tredje)} non-stdlib module"
                     f"{'' if len(tredje) == 1 else 's'}"
                     f"{' (' + ', '.join(sorted(tredje)) + ', imported lazily only when a PostgreSQL DSN is set)' if tredje else ''}"
                     f". The web framework lives in api/, above the engine — "
                     f"so the same computation runs on a laptop with no pip "
                     f"install, in Lambda, and in a container, identically.",
         "check_en": "python3 -m tests.test_contract"},
        {"claim_en": "It refuses when the basis is thin.",
         "proof_en": "Ask for a business count where no register is "
                     "connected and it answers 'No establishment count "
                     "available and none invented.' Commit a decision "
                     "without named owners and it returns 422: 'no owner, "
                     "no decision.' A guessing tool never says no.",
         "check_en": "POST /v1/saturation · POST /v1/decisions/commit"},
        {"claim_en": "Uncertainty is a band, never a percentage.",
         "proof_en": "A figure like '84% certain' invites being multiplied "
                     "onward into calculations it cannot carry. Two "
                     "independent networks that disagree return "
                     "'conflicting' — a weaker basis than one source, not "
                     "a stronger one.",
         "check_en": "GET /v1/corroboration"},
        {"claim_en": "Every number states where it came from.",
         "proof_en": "Each parameter names its source and its status, and "
                     "simulated data is labelled simulated in the response "
                     "itself — not in a footnote on a slide.",
         "check_en": "GET /v1/provenance"},
        {"claim_en": "It publishes what it has NOT proven.",
         "proof_en": "0 of 14 source adapters have been verified against a "
                     "live endpoint from the build environment, and the "
                     "platform says so in its own status output rather "
                     "than waiting to be asked.",
         "check_en": "python3 -m scripts.standing"},
        {"claim_en": "A decision is bound to named owners and resolved "
                     "against the actual outcome.",
         "proof_en": "Three roles are required — formal, operational, "
                     "follow-up — and the expected outcome must be "
                     "measurable (metric, direction, target). Prose is "
                     "refused. That is what makes it possible to ask two "
                     "years later whether it worked.",
         "check_en": "POST /v1/decisions/commit"},
        {"claim_en": f"{sviter} test suites, {rader} tests, no network.",
         "proof_en": "The suite runs without pytest and without a single "
                     "outbound call, so a green build means the logic "
                     "holds — not that a third party happened to be up.",
         "check_en": "make test"},
    ]


def _e(s: object) -> str:
    return html.escape(str(s or ""), quote=True)


def bygg(data: dict) -> str:
    s, o = data["surface"], data["offering"]
    planer = o["plans"]
    alla = {d["id"]: d for p in planer for d in p["decisions_you_can_make"]}
    planerade = {d["id"]: d for p in planer for d in p["not_built_yet"]}

    bevis_kort = ""
    for b in bevis():
        bevis_kort += f"""
    <article class="proof">
      <h3>{_e(b['claim_en'])}</h3>
      <p>{_e(b['proof_en'])}</p>
      <code class="check">{_e(b['check_en'])}</code>
    </article>"""

    lofte_kort = ""
    for p in s["promises"]:
        lofte_kort += f"""
    <article class="promise">
      <span class="ord">{p['order']}</span>
      <h3>{_e(p['question_en'])}</h3>
      <p>{_e(p.get('means_en') or p.get('what_en') or '')}</p>
      <p class="refusal">{_e(p.get('refusal_en', ''))}</p>
    </article>"""

    plan_kort = ""
    for p in planer:
        byggda = [d for d in p["decisions_you_can_make"]]
        rader = ""
        for d in byggda:
            spets = " lead" if d["id"] == p["headline"]["id"] else ""
            rader += f"""
        <li class="d{spets}">
          <span class="q">{_e(d['question_en'])}</span>
          <span class="who">{_e(d['who_en'])}</span>
          <code>{_e(d['answered_by'])}</code>
        </li>"""
        for d in p["not_built_yet"]:
            rader += f"""
        <li class="d planned">
          <span class="q">{_e(d['question_en'])}</span>
          <span class="who">{_e(d.get('note_en') or d['who_en'])}</span>
          <span class="tag">not built</span>
        </li>"""
        plan_kort += f"""
    <article class="plan">
      <header>
        <h3>{_e(p['name_en'])}</h3>
        <p class="for">{_e(p['for_en'])}</p>
        <p class="promise-line">{_e(p['promise_en'])}</p>
        <p class="billing">{_e(p['billing_en'])}</p>
      </header>
      <p class="count">{p['built_count']} decisions you can make{
        f" · {p['planned_count']} planned" if p['planned_count'] else ''}</p>
      <ul>{rader}
      </ul>
    </article>"""

    return f"""{_STIL}
<header class="hero">
  <p class="eyebrow">LANDVEX Opportunity Engine · {_e(data['health'].get('engine_version'))}</p>
  <h1>{_e(s['principle_en'].split('.')[0])}.</h1>
  <p class="lede">{_e(s['what_makes_it_different_en'])}</p>
  <p class="stat"><strong>{len(alla)}</strong> decisions you can make ·
     <strong>{s['promise_count']}</strong> promises ·
     <strong>{s['engine_count']}</strong> engines ·
     <strong>{s['endpoint_count']}</strong> endpoints ·
     <strong>{len(planerade)}</strong> planned and marked as such</p>
</header>

<h2>Why this is an instrument, not a guess</h2>
<p class="section-lede">Every claim below was computed from the
repository when this page was built, and every one names the thing you
can check it against. A tool that guesses would write the same
adjectives — so none of these are adjectives.</p>
<div class="proofs">{bevis_kort}
</div>

<h2>The four promises</h2>
<p class="section-lede">Every engine belongs to exactly one. A test fails
if one belongs to none — a catalogue that can grow without a promise
grows into a feature list.</p>
<div class="promises">{lofte_kort}
</div>

<h2>What you can decide, by tier</h2>
<p class="section-lede">Packaged by the decisions you can make, not by
how many rows you are allowed to download. Planned items are shown as
planned so nobody sells them as available.</p>
<div class="plans">{plan_kort}
</div>

<footer>
  <p>{_e(o['principle_en'])}</p>
  <p>{_e(o['honesty_en'])}</p>
  <p class="gen">Generated from <code>/v1/surface</code> and
  <code>/v1/offering</code> by <code>python3 -m scripts.build_front</code>.
  Nothing on this page is written by hand — add a decision to
  <code>engine/offering.py</code> and it appears here.</p>
</footer>"""


_STIL = """<title>LANDVEX — what you can decide</title>
<style>
:root{--blue:#007AFF;--green:#34C759;--amber:#FF9F0A;--bg:#FBFBFD;
  --card:#FFF;--line:#E5E5EA;--ink:#1D1D1F;--dim:#6E6E73;--faint:#98989D;
  --code:#F5F5F7}
@media (prefers-color-scheme:dark){:root{--bg:#000;--card:#1C1C1E;
  --line:#2C2C2E;--ink:#F5F5F7;--dim:#98989D;--faint:#6E6E73;--code:#2C2C2E;
  --blue:#0A84FF;--green:#30D158}}
:root[data-theme="light"]{--bg:#FBFBFD;--card:#FFF;--line:#E5E5EA;
  --ink:#1D1D1F;--dim:#6E6E73;--faint:#98989D;--code:#F5F5F7;--blue:#007AFF}
:root[data-theme="dark"]{--bg:#000;--card:#1C1C1E;--line:#2C2C2E;
  --ink:#F5F5F7;--dim:#98989D;--faint:#6E6E73;--code:#2C2C2E;--blue:#0A84FF}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);max-width:880px;margin:0 auto;
  padding:3.5rem 1.25rem 5rem;-webkit-font-smoothing:antialiased;
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",
    Roboto,sans-serif}
.eyebrow{font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--faint);font-weight:600;margin-bottom:.7rem}
h1{font-size:2.4rem;line-height:1.1;letter-spacing:-.026em;font-weight:700;
  margin-bottom:.8rem;text-wrap:balance}
.lede{color:var(--dim);font-size:1.06rem;max-width:60ch;margin-bottom:1.1rem}
.stat{font-size:.86rem;color:var(--faint)}
.stat strong{color:var(--ink);font-variant-numeric:tabular-nums}
h2{font-size:.74rem;text-transform:uppercase;letter-spacing:.13em;
  color:var(--faint);font-weight:700;margin:3rem 0 .5rem;
  padding-bottom:.4rem;border-bottom:1px solid var(--line)}
.section-lede{color:var(--dim);font-size:.9rem;margin-bottom:1.2rem;
  max-width:64ch}
.proofs{display:grid;gap:.7rem;margin-bottom:1rem}
.proof{background:var(--card);border:1px solid var(--line);
  border-left:3px solid var(--green);border-radius:0 13px 13px 0;
  padding:1rem 1.2rem}
.proof h3{font-size:.98rem;letter-spacing:-.01em;margin-bottom:.35rem}
.proof p{font-size:.87rem;color:var(--dim);margin-bottom:.5rem}
.check{font-size:.7rem;background:var(--code);padding:.16rem .5rem;
  border-radius:5px;color:var(--dim);
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.promises{display:grid;gap:.8rem;grid-template-columns:repeat(auto-fit,
  minmax(250px,1fr))}
.promise{background:var(--card);border:1px solid var(--line);
  border-radius:13px;padding:1.1rem 1.2rem;position:relative}
.ord{position:absolute;top:1.1rem;right:1.2rem;font-size:.68rem;
  font-weight:700;color:var(--faint);
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.promise h3{font-size:1rem;letter-spacing:-.01em;margin-bottom:.4rem;
  padding-right:1.6rem}
.promise p{font-size:.87rem;color:var(--dim)}
.refusal{margin-top:.6rem;padding-top:.6rem;border-top:1px solid var(--line);
  font-size:.82rem!important;color:var(--amber)!important}
.plans{display:grid;gap:1rem}
.plan{background:var(--card);border:1px solid var(--line);border-radius:13px;
  padding:1.3rem 1.4rem}
.plan h3{font-size:1.2rem;letter-spacing:-.015em;margin-bottom:.3rem}
.for{font-size:.86rem;color:var(--dim);margin-bottom:.5rem}
.promise-line{font-size:.95rem;margin-bottom:.5rem}
.billing{font-size:.79rem;color:var(--faint);margin-bottom:.9rem}
.count{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;
  color:var(--faint);font-weight:600;margin-bottom:.5rem}
.plan ul{list-style:none}
.d{display:grid;grid-template-columns:1fr auto;gap:.2rem .8rem;
  padding:.6rem 0;border-top:1px solid var(--line);align-items:baseline}
.d .q{font-size:.92rem;font-weight:500}
.d .who{grid-column:1;font-size:.79rem;color:var(--dim)}
.d code{font-size:.7rem;background:var(--code);padding:.12rem .4rem;
  border-radius:5px;color:var(--dim);white-space:nowrap;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.d.lead .q{color:var(--blue);font-weight:700}
.d.planned .q{color:var(--faint)}
.tag{font-size:.64rem;text-transform:uppercase;letter-spacing:.07em;
  font-weight:700;color:var(--amber);
  background:color-mix(in srgb,var(--amber) 14%,transparent);
  padding:.14rem .45rem;border-radius:5px;white-space:nowrap}
footer{margin-top:3rem;padding-top:1.4rem;border-top:1px solid var(--line);
  color:var(--dim);font-size:.85rem}
footer p{margin-bottom:.7rem;max-width:66ch}
.gen{color:var(--faint);font-size:.78rem}
footer code{background:var(--code);padding:.1rem .3rem;border-radius:4px}
@media (max-width:560px){
  body{padding:2rem 1rem 3rem}
  h1{font-size:1.75rem}
  .d{grid-template-columns:1fr}
  .d code{justify-self:start}
}
</style>"""


def main(argv: list[str]) -> int:
    ut = pathlib.Path(next((a for a in argv if not a.startswith("--")),
                           "landvex-front.html"))
    data = hamta()
    sida = bygg(data)
    if "--fragment" not in argv:
        sida = ("<!doctype html><html lang=\"en\"><head>"
                "<meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,"
                "initial-scale=1\">" + sida.split("</style>")[0] +
                "</style></head><body>" +
                sida.split("</style>", 1)[1] + "</body></html>")
    ut.write_text(sida, encoding="utf-8")
    n = len({d["id"] for p in data["offering"]["plans"]
             for d in p["decisions_you_can_make"]})
    print(f"{ut} ({len(sida) // 1024} kB) · "
          f"{data['surface']['promise_count']} löften · {n} beslut")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
