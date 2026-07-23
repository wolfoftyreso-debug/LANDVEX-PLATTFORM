"""Bygger en fristående demo av portalen med förberäknade motorsvar.

    python3 -m scripts.build_demo [utfil]

Demon är exakt frontend/index.html men med api() utbytt mot uppslag i
inbakade svar – all data kommer från de riktiga motorerna vid bygget.
Används för delning/visning utan server; live-läget är alltid
python3 -m api.dev_server.
"""
from __future__ import annotations

import json
import pathlib
import sys

from api.catalog import API_CATALOG
from api.health import build_health
from api.licensing import plans_catalog
from engine.ask import ask
from engine.datasources.base import Resolver
from engine.datasources.mock import MockSource
from engine.gaps import gap_analysis
from engine.indices import city_assessment, index_catalog, index_map
from engine.markets import MARKETS, market_catalog
from engine.models import Location
from engine.plan import establishment_plan
from engine.profile import profile_from_dict, profile_options
from engine.risk import assess
from engine.scan import SCAN_LEVEL_OPTIONS, scan
from engine.workforce import (OCCUPATIONS, forecast, national_map, simulate,
                              occupation_catalog)

FRAGOR = [
    "Vilka är de fem största affärsmöjligheterna i Örebro just nu?",
    "Vilka är de tre största affärsmöjligheterna i Göteborg?",
    "Var i Europa är det störst brist på elektriker?",
    "Var i världen är bristen på snickare störst?",
    "Var är det bäst att starta ett VVS-företag i Tyskland?",
    "Vilket land är bäst för en svensk snickare att flytta till?",
    "Vilka yrkesgrupper saknas mest i Umeå de kommande fem åren?",
    "Vilka yrkesgrupper saknas mest i Berlin?",
    "Vilken amerikansk delstat behöver flest sjuksköterskor de kommande tio åren?",
    "Var i Sverige är behovet av sjuksköterskor störst?",
    "Var ska jag öppna café?",
    "Hur riskabelt är det att starta gym i Solna?",
    "Var finns störst obalans för bilverkstäder?",
    "Gör en etableringsplan för bilverkstad i Skellefteå.",
    "Var i Sverige finns flest djurägare?",
    "Hur ser målgrupperna ut i Umeå?",
    "Vilken region har flest värmepumpar som närmar sig utbytesålder?",
    "Var är det bäst att starta ett företag som servar laddboxar?",
    "Hur ser servicebehovet ut i Umeå?",
    "Var kommer behovet av kyltekniker att öka de kommande fem åren?",
]
# Demoprincip: ALLT som går att välja i demon är förberäknat – val utan
# data (fler marknader, andra målår) erbjuds inte alls. Därför bakas
# alla vertikaler och alla yrken för demomarknaderna.
DEMO_MARKETS = ("se", "de")


def _strip(f: dict) -> dict:
    f = dict(f)
    f["prognoser"] = [{k: v for k, v in p.items() if k != "bana"}
                      for p in f["prognoser"]]
    return f


def build(out_path: str) -> None:
    from engine.verticals import VERTICALS
    demo: dict = {
        # Endast bakade val erbjuds: en analysnivå, två marknader.
        "options": {**profile_options(),
                    "scan_levels": [SCAN_LEVEL_OPTIONS[0]]},
        "occupations": occupation_catalog(),
        "markets": [m for m in market_catalog() if m["id"] in DEMO_MARKETS],
        "ask": {q: ask(q) for q in FRAGOR},
        "scans": {}, "wf_maps": {}, "forecasts": {}, "simulate": {},
        "risk": {}, "plans": {}, "gaps": {},
        "index_catalog": index_catalog(),
        "index_maps": {}, "assessments": {},
        "plans_catalog": plans_catalog(),
        # Om systemet: demon kör enbart på förberäknad/simulerad data,
        # därför visas mock-kedjan – inte produktionens källstatus.
        "health": build_health(Resolver([MockSource()]), None),
        "catalog": API_CATALOG,
    }
    for market in DEMO_MARKETS:
        for vid in VERTICALS:
            demo["gaps"][f"{market}:{vid}"] = gap_analysis(
                vid, market=market, top_n=5)
    for market in DEMO_MARKETS:
        for ix in index_catalog():
            demo["index_maps"][f"{market}:{ix['id']}"] = index_map(
                ix["id"], market=market)
        for kod, *_ in MARKETS[market].regions:
            demo["assessments"][f"{market}:{kod}"] = city_assessment(
                kod, market=market)
    # Följdfrågor i demon pekar alltid på bakade frågor.
    for q, svar in demo["ask"].items():
        svar["forslag_sv"] = [f for f in FRAGOR if f != q][:3]

    for market in DEMO_MARKETS:
        for vid in VERTICALS:
            res = scan(profile_from_dict({"vertical_id": vid}), top_n=5,
                       market=market)
            demo["scans"][f"{market}:{vid}"] = res
            for h in res["hotspots"]:
                key = f"{h['lat']:.3f}:{h['lon']:.3f}:{vid}"
                if key not in demo["risk"]:
                    demo["risk"][key] = assess(
                        Location(h["lat"], h["lon"], address=h["lage_sv"]), vid)
                demo["plans"][f"{market}:{h['kommun_kod']}:{vid}"] = \
                    establishment_plan(h["kommun_kod"], vid, market=market)
        for occ in OCCUPATIONS:
            demo["wf_maps"][f"{market}:{occ}"] = national_map(
                occ, 2035, market=market)
            for kod, *_ in MARKETS[market].regions:
                demo["forecasts"][f"{market}:{kod}:{occ}"] = _strip(
                    forecast(kod, 2035, [occ], market=market))
                s = simulate(kod, occ, 30, 2035, market=market)
                demo["simulate"][f"{market}:{kod}:{occ}"] = {
                    k: v for k, v in s.items()
                    if k not in ("bana_utan", "bana_med")}

    html = (pathlib.Path(__file__).resolve().parent.parent /
            "frontend" / "index.html").read_text(encoding="utf-8")
    old_api = '''async function api(path, body) {
  // API-nyckeln från Inställningar följer med varje anrop (skyddat live-API).
  const huvud = {};
  if (INSTALL.nyckel) huvud["X-API-Key"] = INSTALL.nyckel;
  const res = await fetch(path, body
    ? { method: "POST",
        headers: { "Content-Type": "application/json", ...huvud },
        body: JSON.stringify(body) }
    : { headers: huvud });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.error || res.status);
  return data;
}'''
    assert old_api in html, "api() hittades inte i frontend/index.html"
    new_api = '''const DEMOFEL = "Den här kombinationen är inte förberäknad i demon – live-API:t (python3 -m api.dev_server) svarar på allt.";
function qp(path, key) { const m = path.match(new RegExp(key + "=([^&]*)")); return m ? m[1] : null; }
async function api(path, body) {
  const D = window.DEMO;
  await new Promise(r => setTimeout(r, 150));
  if (path === "/v1/profile-options") return D.options;
  if (path === "/v1/workforce/occupations") return D.occupations;
  if (path === "/v1/markets") return D.markets;
  if (path === "/v1/ask") {
    const svar = D.ask[(body.question || "").trim()];
    if (svar) return svar;
    return { intent: "hjalp", rader: [], caveats_sv: [],
      svar_sv: "Demoläget har förberäknade svar för frågorna nedan – live-API:t tolkar fria frågor.",
      forslag_sv: Object.keys(D.ask) };
  }
  if (path === "/v1/scan") {
    const r = D.scans[`${body.market || "se"}:${(body.profile || {}).vertical_id}`];
    if (!r) throw new Error(DEMOFEL);
    const kopia = JSON.parse(JSON.stringify(r));
    kopia.caveats_sv.unshift("Demo: bransch och marknad styr det förberäknade svepet – övriga profilfält påverkar inte resultatet här.");
    return kopia;
  }
  if (path.startsWith("/v1/workforce/map")) {
    const r = D.wf_maps[`${qp(path, "market") || "se"}:${qp(path, "occupation_id")}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/workforce/forecast") {
    const r = D.forecasts[`${body.market || "se"}:${body.kommun_kod}:${(body.occupation_ids || [])[0]}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/workforce/simulate") {
    const r = D.simulate[`${body.market || "se"}:${body.kommun_kod}:${body.occupation_id}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/plans") return D.plans_catalog;
  if (path === "/health") return D.health;
  if (path === "/v1/catalog") return D.catalog;
  if (path === "/v1/gaps") {
    const r = D.gaps[`${body.market || "se"}:${body.vertical}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/indices") return D.index_catalog;
  if (path.startsWith("/v1/indices/map")) {
    const r = D.index_maps[`${qp(path, "market") || "se"}:${qp(path, "index_id")}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/indices/assess") {
    const r = D.assessments[`${body.market || "se"}:${body.kommun_kod}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/plan") {
    const r = D.plans[`${body.market || "se"}:${body.kommun_kod}:${body.vertical}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/risk") {
    const r = D.risk[`${body.lat.toFixed(3)}:${body.lon.toFixed(3)}:${body.vertical}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  throw new Error(DEMOFEL);
}'''
    html = html.replace(old_api, new_api)
    # Demon erbjuder bara val som har data: ett målår, låst simulering.
    html = html.replace(
        '<option>2028</option><option>2030</option><option>2032</option>'
        '<option selected>2035</option><option>2038</option>'
        '<option>2040</option><option>2045</option>',
        '<option selected>2035</option>')
    html = html.replace(
        '<input type="number" min="0" value="30" id="simN_${kod}">',
        '<input type="number" value="30" id="simN_${kod}" readonly '
        'title="Demon simulerar 30 platser/år – live-läget tar valfritt antal">')
    # Guidens platser-fråga är låst till det bakade värdet 30.
    assert 'data-guide="platser" min="0"' in html, \
        "guidens platser-fält hittades inte i frontend/index.html"
    html = html.replace(
        '<input type="number" id="guideInput" data-guide="platser" min="0" ` +\n'
        '      `value="${nuv ? JSON.parse(nuv) : falt.standard}">',
        '<input type="number" id="guideInput" data-guide="platser" readonly '
        'title="Demon simulerar 30 platser/år – live-läget tar valfritt antal" ` +\n'
        '      `value="30">')
    # Topplistorna är bakade med fem träffar – andra top-N erbjuds inte.
    assert '<select id="instTopN">' in html, \
        "instTopN hittades inte i frontend/index.html"
    html = html.replace(
        '<select id="instTopN"><option>3</option><option selected>5</option>'
        '<option>8</option><option>10</option></select>',
        '<select id="instTopN"><option selected>5</option></select>')
    html = html.replace("<title>LANDVEX · Opportunity Engine</title>",
                        "<title>LANDVEX · Opportunity Engine (demo)</title>")
    html = html.replace("</header>", """</header>
<div style="background:rgba(91,141,239,.12);border-bottom:1px solid var(--line);color:var(--muted);font-size:12px;padding:6px 20px">
  Statisk demo (förberäknade motorsvar, all data simulerad och märkt därefter).
  Live-läge: <code style="color:var(--text)">python3 -m api.dev_server</code>
</div>""")
    payload = json.dumps(demo, ensure_ascii=False)
    html = html.replace('<script>\n"use strict";',
                        f'<script>window.DEMO = {payload};</script>\n'
                        f'<script>\n"use strict";', 1)
    out = pathlib.Path(out_path)
    out.write_text(html, encoding="utf-8")
    print(f"demo: {out} ({round(out.stat().st_size / 1024)} kB) · "
          f"{len(demo['ask'])} frågor · {len(demo['scans'])} svep · "
          f"{len(demo['wf_maps'])} kartor · {len(demo['forecasts'])} prognoser · "
          f"{len(demo['gaps'])} gap-analyser")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "landvex-demo.html")
