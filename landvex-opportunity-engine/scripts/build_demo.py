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
from api.health import build_health, source_status
from integrations.aamos import (AamosClient, agent_chat_safe,
                                agents, platform_status, watch)
from api.licensing import plans_catalog
from engine.ask import ask
from engine.datasources.base import Resolver
from engine.datasources.mock import MockSource
from engine.gaps import gap_analysis
from engine.indices import city_assessment, index_catalog, index_map
from engine.markets import MARKETS, market_catalog
from engine.models import Location
from engine.opportunity_intel import opportunity_intel
from engine.risk_intel import risk_intelligence
from engine.plan import establishment_plan
from engine.profile import profile_from_dict, profile_options
from engine.risk import assess
from engine.scan import SCAN_LEVEL_OPTIONS, scan
from engine.workforce import (OCCUPATIONS, forecast, national_map, simulate,
                              occupation_catalog)

FRAGOR = [
    "What are the five biggest business opportunities in Dallas right now?",
    "What are the three biggest business opportunities in Seattle?",
    "Which US metro region will need the most nurses over the next ten years?",
    "Where in the US is the shortage of electricians greatest?",
    "Where should I open a café?",
    "How risky is it to start a gym in Miami?",
    "Where is the imbalance greatest for car repair shops?",
    "Create an establishment plan for a car repair shop in Austin.",
    "Where in the US are there the most pet owners?",
    "What do the target groups look like in Boston?",
    "Which region has the most heat pumps approaching replacement age?",
    "Where is the best place to start a company servicing EV chargers?",
    "What does the service demand look like in Denver?",
    "Where will the need for refrigeration technicians increase over the next five years?",
    "Where in Europe is the shortage of electricians greatest?",
    "Where in the world is the shortage of carpenters greatest?",
    "Which country is best for an American electrician to move to?",
    "Where in Sweden is the need for nurses greatest?",
    "Which occupations are missing most in Stockholm?",
    "Where is the best place to start a plumbing company in Germany?",
]
# Demoprincip: ALLT som går att välja i demon är förberäknat – val utan
# data (fler marknader, andra målår) erbjuds inte alls. Därför bakas
# alla vertikaler och alla yrken för demomarknaderna.
# Marknader som förberäknas i den statiska demon. Hela marknadslistan
# (alla 27 EU-länder + alla delstater) visas ändå i menyn – icke-bakade
# marknader hänvisar ärligt till live-API:t.
DEMO_MARKETS = ("us", "se", "de")


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
        # Hela marknadskatalogen visas i menyn (alla EU-länder + delstater);
        # 'demo_precomputed' markerar vilka som är förberäknade i demon.
        "markets": [{**m, "demo_precomputed": m["id"] in DEMO_MARKETS}
                    for m in market_catalog()],
        "ask": {q: ask(q) for q in FRAGOR},
        "scans": {}, "wf_maps": {}, "forecasts": {}, "simulate": {},
        "risk": {}, "plans": {}, "gaps": {}, "opportunities": {},
        "risk_intel": {},
        "index_catalog": index_catalog(),
        "index_maps": {}, "assessments": {},
        "plans_catalog": plans_catalog(),
        # Om systemet: demon kör enbart på förberäknad/simulerad data,
        # därför visas mock-kedjan – inte produktionens källstatus.
        "health": build_health(Resolver([MockSource()]), None),
        "catalog": API_CATALOG,
        # AAMOS-integrationen: demon visar det ärliga ej-anslutna läget.
        "platform_status": platform_status(
            AamosClient(base_url=""), Resolver([MockSource()]), None,
            build_health, source_status),
        "watch": watch(AamosClient(base_url=""), Resolver([MockSource()]),
                       source_status),
        "agents": agents(AamosClient(base_url="")),
        "agent_chat": agent_chat_safe(AamosClient(base_url=""), ""),
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
        svar["forslag_en"] = [f for f in FRAGOR if f != q][:3]

    from engine.specialization import specializations_for
    for market in DEMO_MARKETS:
        for vid in VERTICALS:
            # Generellt läge + varje specialisering (personlig score).
            specs = [None] + [s["id"] for s in specializations_for(vid)]
            for sp in specs:
                res = scan(profile_from_dict(
                    {"vertical_id": vid,
                     **({"specialization": sp} if sp else {})}),
                    top_n=5, market=market)
                demo["scans"][f"{market}:{vid}:{sp or 'generell'}"] = res
                for h in res["hotspots"]:
                    key = f"{h['lat']:.3f}:{h['lon']:.3f}:{vid}"
                    if key not in demo["risk"]:
                        demo["risk"][key] = assess(
                            Location(h["lat"], h["lon"],
                                     address=h["lage_en"]), vid)
                    demo["plans"][f"{market}:{h['kommun_kod']}:{vid}"] = \
                        establishment_plan(h["kommun_kod"], vid, market=market)
                    okey = f"{h['lat']:.3f}:{h['lon']:.3f}:{vid}:{sp or 'generell'}"
                    if okey not in demo["opportunities"]:
                        demo["opportunities"][okey] = opportunity_intel(
                            Location(h["lat"], h["lon"], address=h["lage_en"]),
                            vid, specialization=sp, market=market)
                    if okey not in demo["risk_intel"]:
                        demo["risk_intel"][okey] = risk_intelligence(
                            Location(h["lat"], h["lon"], address=h["lage_en"]),
                            vid, specialization=sp, market=market)
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
    new_api = '''const DEMOFEL = "This combination is not precomputed in the demo – the live API (python3 -m api.dev_server) answers everything.";
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
    return { intent: "hjalp", rader: [], caveats_en: [],
      svar_en: "The demo has precomputed answers for the questions below – the live API interprets free-form questions.",
      forslag_en: Object.keys(D.ask) };
  }
  if (path === "/v1/scan") {
    const pf = body.profile || {};
    const sp = pf.specialization || "generell";
    const r = D.scans[`${body.market || "us"}:${pf.vertical_id}:${sp}`]
      || D.scans[`${body.market || "us"}:${pf.vertical_id}:generell`];
    if (!r) throw new Error(DEMOFEL);
    const kopia = JSON.parse(JSON.stringify(r));
    kopia.caveats_en.unshift("Demo: industry, specialization and market drive the precomputed sweep – the other profile fields do not affect this result.");
    return kopia;
  }
  if (path.startsWith("/v1/workforce/map")) {
    const r = D.wf_maps[`${qp(path, "market") || "us"}:${qp(path, "occupation_id")}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/workforce/forecast") {
    const r = D.forecasts[`${body.market || "us"}:${body.kommun_kod}:${(body.occupation_ids || [])[0]}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/workforce/simulate") {
    const r = D.simulate[`${body.market || "us"}:${body.kommun_kod}:${body.occupation_id}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/plans") return D.plans_catalog;
  if (path === "/health") return D.health;
  if (path === "/v1/catalog") return D.catalog;
  if (path === "/v1/platform/status") return D.platform_status;
  if (path === "/v1/watch") return D.watch;
  if (path === "/v1/agents") return D.agents;
  if (path === "/v1/agents/chat") return D.agent_chat;
  if (path === "/v1/gaps") {
    const r = D.gaps[`${body.market || "us"}:${body.vertical}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/indices") return D.index_catalog;
  if (path.startsWith("/v1/indices/map")) {
    const r = D.index_maps[`${qp(path, "market") || "us"}:${qp(path, "index_id")}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/indices/assess") {
    const r = D.assessments[`${body.market || "us"}:${body.kommun_kod}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/plan") {
    const r = D.plans[`${body.market || "us"}:${body.kommun_kod}:${body.vertical}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/risk") {
    const r = D.risk[`${body.lat.toFixed(3)}:${body.lon.toFixed(3)}:${body.vertical}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/opportunities") {
    const sp = body.specialization || "generell";
    const r = D.opportunities[`${body.lat.toFixed(3)}:${body.lon.toFixed(3)}:${body.vertical}:${sp}`]
      || D.opportunities[`${body.lat.toFixed(3)}:${body.lon.toFixed(3)}:${body.vertical}:generell`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/risk-intelligence") {
    const sp = body.specialization || "generell";
    const r = D.risk_intel[`${body.lat.toFixed(3)}:${body.lon.toFixed(3)}:${body.vertical}:${sp}`]
      || D.risk_intel[`${body.lat.toFixed(3)}:${body.lon.toFixed(3)}:${body.vertical}:generell`];
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
        'title="The demo simulates 30 places/yr – the live system takes any number">')
    # Guidens platser-fråga är låst till det bakade värdet 30.
    assert 'data-guide="platser" min="0"' in html, \
        "guidens platser-fält hittades inte i frontend/index.html"
    html = html.replace(
        '<input type="number" id="guideInput" data-guide="platser" min="0" ` +\n'
        '      `value="${nuv ? JSON.parse(nuv) : falt.standard}">',
        '<input type="number" id="guideInput" data-guide="platser" readonly '
        'title="The demo simulates 30 places/yr – the live system takes any number" ` +\n'
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
  Static demo (precomputed engine responses; all data simulated and labeled as such).
  Live mode: <code style="color:var(--text)">python3 -m api.dev_server</code>
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
