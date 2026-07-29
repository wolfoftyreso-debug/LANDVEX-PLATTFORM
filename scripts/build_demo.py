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
from engine.accountability import ledger as accountability_ledger
from engine.analysis import register as analysis_register
from engine.corroboration import catalog as corroboration_cat
from engine.entrypoints import entrypoints
from engine.coverage import coverage
from engine.land import assess as land_assess
from engine.mrai import mrai
from engine.export import FORMATS as EXPORT_FORMATS
from engine.export import catalog as export_catalog
from engine.pushes import PushRefused
from engine.pushes import catalog as pushes_catalog
from engine.pushes import preview as push_preview
from engine.wages import wage
from scripts.seed_inspections import payload as inspections_payload
from engine.chain import chain_overview
from engine.scan import SCAN_LEVEL_OPTIONS, scan
from engine.surface import surface
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

# Storleken på den statiska demon är matrisen marknader × vertikaler ×
# regioner × yrken. Full matris ger ~42 MB, vilket inte går att dela och
# inte behöver delas: en rundvandring behöver DJUP i en marknad, inte
# bredd över tre. `--lite` bakar en marknad och de vanligaste
# vertikalerna. Icke-bakade val hänvisar ärligt till live-API:t, precis
# som icke-bakade marknader alltid gjort — ingenting påstås vara
# förberäknat som inte är det.
# US, inte SE: konsolens standardmarknad är us, och ett demo vars
# FÖRSTA klick svarar "den här kombinationen är inte förberäknad" visar
# ingenting av produkten. Den baserade marknaden måste vara den som är
# vald när sidan öppnas.
LITE_MARKETS = ("us",)
LITE_VERTICALS = ("cafe", "restaurang", "frisor", "elektriker", "gym",
                  "bageri", "tandlakare", "bilverkstad")
# Prognoserna är den tyngsta posten: regioner × yrken, två gånger
# (prognos + simulering). Sex yrken i stället för 21 räcker för att visa
# vad arbetskraftsmotorn gör.
LITE_OCCUPATIONS = ("elektriker", "vvs_montor", "snickare", "larare",
                    "sjukskoterska", "underskoterska")


def _strip(f: dict) -> dict:
    f = dict(f)
    f["prognoser"] = [{k: v for k, v in p.items() if k != "bana"}
                      for p in f["prognoser"]]
    return f


# Analyze-flikens regionval — samma tre per marknad som frontend visar.
_ANALYS_REGIONER = {"se": ("0180", "1480", "1280"),
                    "us": ("us-newyork", "us-losangeles", "us-chicago")}


def _bake_sponsorship() -> dict:
    """Sponsorportalen: katalog, EN exempelkampanj, k-golvad statistik
    och uppdragsförhandsvisning — allt ur motorn vid bygget, inget ur
    något lager. Fullbordandena är simulerade och regionerna VALDA så
    att k-golvet syns i demon: en cell över golvet visas, resten
    undertrycks och räknas — det är poängen med ytan.
    """
    from engine import sponsorship as SP

    SP.reset()
    kamp = SP.campaign(
        "garmin-trail-2026", "Garmin Nordic", "content",
        "Photograph your Garmin watch on a trail run in daylight",
        budget=25000.0, currency="SEK",
        rewards=({"kind": "gift_card", "amount": 250},
                 {"kind": "loyalty_points", "points": 500}),
        market="se", max_per_day=40,
        rights_agreement_ref="QZ-RIGHTS-2026-018",
        co_sponsors=({"name_en": "Garmin Nordic", "share": 0.7},
                     {"name_en": "Runners' World SE", "share": 0.3}),
        tenant="demo")
    kamp["ordered"] = 32
    kamp["spent"] = 8000.0
    SP.save_campaign(kamp)
    t0 = 1753700000.0  # fast simulerad tidsaxel — demon är fryst ändå
    fördelning = (("0180", 14), ("1480", 6), ("1280", 3), ("1880", 2))
    i = 0
    for region, antal in fördelning:
        for _ in range(antal):
            i += 1
            SP.save_completion(SP.completion(
                kamp["id"], f"qz-demo-{i:03d}", region_code=region,
                quality_band="good" if i % 4 else "acceptable",
                settlement_ref=f"qz-settle-{i:03d}", tenant="demo",
                completed_at=t0 + i * 86400 / 4))
    ut = {
        "overview": {**SP.catalog(), "campaigns": [kamp]},
        "stats": {kamp["id"]: SP.stats(kamp["id"], tenant="demo")},
        "mission": {kamp["id"]: SP.mission_body(kamp,
                                                region_code="0180")},
    }
    SP.reset()
    return ut


def _bake_krypin() -> dict:
    """Kryp-in-katalogerna: vad som GÅR att koppla. Kundens egna rader
    (nycklar, profil, personal) hör hemma bakom inloggning i live-läget
    — demon visar valrymden och vägrar skrivningarna."""
    from engine import company as CO
    from engine import connections as CN
    from engine import credentials as CR
    from engine import deliveries as DL
    from engine import staff as ST
    return {
        "connections": {**CN.catalog(), "connections": []},
        "company": {**CO.catalog(), "profile": None},
        "staff": {**ST.catalog(), "staff": []},
        "credentials": CR.catalog(),
        "deliveries": {**DL.catalog(), "deliveries": []},
    }


def _bake_pushes() -> dict:
    """Pushgeneratorns previews för dataset × format.

    Tenant-bundna datamängder vägras med skälet i stället för att
    förhandsvisas ur ett tomt lager: "0 rader" ur en demo utan kundlager
    hade sett ut som en kund utan objekt — ett falskt kvitto. Vägrade
    format bär exportmotorns eget besked.
    """
    ut = {}
    for d in export_catalog()["datasets"]:
        for fmt in EXPORT_FORMATS:
            nyckel = f"{d['id']}:{fmt}"
            if d.get("tenant_scoped"):
                ut[nyckel] = {"refused_en": (
                    f"{d['id']} is tenant-scoped: the static demo carries "
                    f"no customer store, and previewing an empty store "
                    f"would look like a customer with zero objects. The "
                    f"live API answers with your tenant's own rows.")}
                continue
            try:
                ut[nyckel] = push_preview(d["id"], fmt)
            except PushRefused as e:
                ut[nyckel] = {"refused_en": str(e)}
    return ut


def _bake_saturation(marknader, vertikaler) -> dict:
    from engine.saturation_scan import market_saturation
    ut = {}
    for m in marknader:
        for vid in vertikaler:
            for kod in _ANALYS_REGIONER.get(m, ()):
                ut[f"{vid}:{kod}:{m}"] = market_saturation(
                    vid, kod, market=m)
    return ut


def _bake_merit(marknader) -> dict:
    from engine.merit_scan import market_merit, region_merit
    ut = {}
    for m in marknader:
        ut[m] = market_merit(m, top_n=10)
        for kod in _ANALYS_REGIONER.get(m, ()):
            ut[f"{m}:{kod}"] = region_merit(kod, market=m)
    return ut


def _bake_livability(marknader, yrken) -> dict:
    from engine.livability_scan import livability_ranking
    hushall = ("single", "couple_children", "senior")
    ut = {}
    for m in marknader:
        for occ in yrken:
            for hh in hushall:
                ut[f"{occ}:{hh}:{m}"] = livability_ranking(
                    occ, hh, markets=[m], top_n=8)
    return ut


def build(out_path: str, lite: bool = False,
          fragment: bool = False) -> None:
    from engine.verticals import VERTICALS
    marknader = LITE_MARKETS if lite else DEMO_MARKETS
    vertikaler = ([v for v in VERTICALS if v in LITE_VERTICALS] if lite
                  else VERTICALS)
    yrken = ([o for o in OCCUPATIONS if o in LITE_OCCUPATIONS] if lite
             else OCCUPATIONS)
    demo: dict = {
        # Endast bakade val erbjuds: en analysnivå, två marknader.
        "options": {**profile_options(),
                    "scan_levels": [SCAN_LEVEL_OPTIONS[0]]},
        "occupations": occupation_catalog(),
        # Hela marknadskatalogen visas i menyn (alla EU-länder + delstater);
        # 'demo_precomputed' markerar vilka som är förberäknade i demon.
        "markets": [{**m, "demo_precomputed": m["id"] in marknader}
                    for m in market_catalog()],
        "ask": {q: ask(q) for q in FRAGOR},
        "scans": {}, "wf_maps": {}, "forecasts": {}, "simulate": {},
        "risk": {}, "plans": {}, "gaps": {}, "opportunities": {},
        "risk_intel": {},
        # Fyra löften, hela katalogen under dem — det som intron nu
        # visar i stället för att en människa räknar fyrtiotalet motorer
        # själv. Bakad, inte en levande /v1/surface-fråga: samma regel
        # som resten av demon.
        "surface": surface(),
        # De fyra avsikterna + de två ärliga kedjorna — samma bakningsregel.
        "chain": chain_overview(),
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
        # Demokunden för kontrollmodulen: flaggleverantören i Stockholm.
        # Byggs ur fixturens egna listor, aldrig ur ett lager — demon ska
        # inte kunna råka visa en riktig kunds objekt och adresser.
        "inspections": inspections_payload(),
        # Pushgeneratorn: valrymden + exakta previews per dataset×format.
        # Frysta vid bygget — precis som allt annat i demon.
        "pushes_catalog": pushes_catalog(),
        "pushes_preview": _bake_pushes(),
        # Sponsorportalen: exempelkampanjen och dess k-golvade statistik.
        "sponsorship": _bake_sponsorship(),
        # Kryp-in: katalogerna bakas, kundens egna rader finns inte i en
        # statisk demo — tomma listor är ärliga, skrivningar vägras.
        "krypin": _bake_krypin(),
        # Medie- & politikintelligensen. Vägran bakas som den är: MRAI
        # utan skördad referensdata SKA säga insufficient, registret
        # utan körd sökning SKA vara tomt med sitt quiet_en — demon
        # visar det ärliga läget, inte ett friserat.
        "entrypoints": entrypoints(),
        # Analyze-fliken: motorerna som inte syns någon annanstans.
        # Nycklarna speglar flikens val (tre regioner per marknad) —
        # allt annat svarar DEMOFEL och hänvisar till live-API:t.
        "analyze_saturation": _bake_saturation(marknader, vertikaler),
        "analyze_merit": _bake_merit(marknader),
        "analyze_livability": _bake_livability(marknader, yrken),
        "analyze_wages": {f"{o}:{m}": wage(o, m)
                          for m in marknader for o in yrken},
        "analyze_coverage": {m: coverage(m) for m in ("se", "us", "de")},
        "analyze_land": {f"{m}:{kod}": land_assess(kod, market=m)
                         for m in marknader
                         for kod in _ANALYS_REGIONER.get(m, ())},
        "mrai": {m: mrai(m) for m in ("se", "us", "de")},
        "analysis": {m: analysis_register(market=m)
                     for m in ("se", "us", "de")},
        "corroboration": corroboration_cat(),
        "ledger": accountability_ledger(),
    }
    for market in marknader:
        for vid in vertikaler:
            demo["gaps"][f"{market}:{vid}"] = gap_analysis(
                vid, market=market, top_n=5)
    for market in marknader:
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
    for market in marknader:
        for vid in vertikaler:
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
        for occ in yrken:
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
  if (path === "/v1/entrypoints") return D.entrypoints;
  if (path.startsWith("/v1/mrai")) {
    const r = D.mrai[qp(path, "market") || "se"];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path.startsWith("/v1/analysis")) {
    const r = D.analysis[qp(path, "market") || "se"];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/corroboration") return D.corroboration;
  if (path === "/v1/decisions/ledger") return D.ledger;
  if (path === "/v1/saturation") {
    const r = D.analyze_saturation[`${body.vertical}:${body.region}:${body.market || "se"}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/merit") {
    const r = body.region ? D.analyze_merit[`${body.market || "se"}:${body.region}`]
                          : D.analyze_merit[body.market || "se"];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/livability") {
    const r = D.analyze_livability[`${body.occupation}:${body.household || "single"}:${(body.markets || ["se"])[0]}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/wages/lookup") {
    const r = D.analyze_wages[`${body.occupation}:${body.market || "se"}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/land/assess") {
    const r = D.analyze_land[`${body.market || "se"}:${body.region_code}`];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path.startsWith("/v1/coverage")) {
    const r = D.analyze_coverage[qp(path, "market") || "se"];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/ask") {
    const q = (body.question || "").trim();
    const svar = D.ask[q];
    if (svar) return svar;
    // Best-effort client-side match for free-form questions (EN + SV):
    // detect an industry (+ optional market) and answer from the baked sweep.
    const ql = " " + q.toLowerCase() + " ";
    const SV = ["sverige","sweden","svensk","stockholm","göteborg","goteborg",
                "malmö","malmo","uppsala","västerås","vasteras","örebro","län","kommun"];
    const DE = ["tyskland","germany","tysk","berlin","münchen","munchen","munich",
                "hamburg","frankfurt","köln","koln","cologne"];
    // Swedish-language markers → default to Sweden when no other place is named.
    const SVLANG = [" ska "," öppna "," vart "," var "," hur "," bäst "," företag ",
                    " jobb "," starta "," för "," och "," att "];
    const isSv = SVLANG.some(w => ql.includes(w));
    let market = DE.some(w => ql.includes(w)) ? "de"
               : (SV.some(w => ql.includes(w)) || isSv) ? "se" : "us";
    const SYN = {
      elektriker:["elektriker","electrician"," el ","laddbox","charger","solcell","solar","charging"],
      vvs:["vvs","plumb","rör","värmepump","heat pump"],
      bygg:["bygg","snickare","construction","carpenter","builder"],
      frisor:["frisör","frisor","hair","barber","salong"],
      gym:["gym","fitness","träning"],
      restaurang:["restaurang","restaurant","krog"],
      cafe:["café","cafe","kafé","kafe","coffee"," fik"],
      tandlakare:["tandläkare","tandlakare","dentist","tandvård"],
      bilverkstad:["bilverkstad"," bil ","verkstad","car repair","auto","mekaniker"],
      veterinar:["veterinär","veterinar"," vet ","djurklinik"],
      malare:["målare","malare","painter","måleri"],
      apotek:["apotek","pharmacy"], bageri:["bageri","bakery","bagare"],
      optiker:["optiker","optician"], forskola:["förskola","forskola","preschool"],
      stadfirma:["städ","cleaning"], lager:["lager","warehouse","logistik"]
    };
    let vid = null;
    for (const o of (D.options.vertical_id||[]))
      if (ql.includes(o.id) || ql.includes((o.label_en||"").toLowerCase())) { vid = o.id; break; }
    if (!vid) for (const [id, words] of Object.entries(SYN))
      if (words.some(w => ql.includes(w))) { vid = id; break; }
    if (vid) {
      const scan = D.scans[`${market}:${vid}:generell`] || D.scans[`us:${vid}:generell`];
      if (scan) {
        const mlabel = (D.markets.find(m=>m.id===scan.market)||{}).label_en || scan.market;
        return {
          intent: "basta_lage_vertikal",
          svar_en: `Top opportunities for ${scan.vertical_label_en.toLowerCase()} in ${mlabel} (matched from your question).`,
          rader: scan.hotspots.map(h => ({
            id: h.kommun_kod, label_en: h.lage_en, score: h.opportunity_score,
            detalj: { motivering_en: h.motivering_en, faktorer: h.factors } })),
          karta: { typ: "heatmap", bbox: scan.bbox, hotspots: scan.hotspots, heatmap: scan.heatmap },
          forslag_en: Object.keys(D.ask).slice(0, 3),
          caveats_en: ["Demo: your free-form question was matched to the precomputed " +
            scan.vertical_label_en.toLowerCase() + " sweep for " + mlabel +
            ". The live API parses the whole question — place, count, target year and intent."]
        };
      }
    }
    return { intent: "hjalp", rader: [], caveats_en: [],
      svar_en: "The demo has precomputed answers for the questions below – the live API interprets any free-form question.",
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
  if (path === "/v1/inspections/compliance") return D.inspections.compliance;
  if (path === "/v1/inspections/exceptions") return D.inspections.exceptions;
  if (path === "/v1/routines") {
    // LÄSNINGAR svaras ur fixturen. En SKRIVNING (body) får aldrig se
    // lagrad ut i demon — "✓ stored" utan lager är exakt den sortens
    // falska kvitto plattformen vägrar ge någon annanstans.
    if (body) throw new Error(DEMOFEL);
    return D.inspections.routines;
  }
  if (path === "/v1/assets") {
    if (body) throw new Error(DEMOFEL);
    return D.inspections.assets;
  }
  if (path === "/v1/infrastructure") return D.inspections.infra_catalog;
  if (path === "/v1/infrastructure/status") {
    // En LÄSNING med body: bakad status per seedat objekt. Åldrarna är
    // byggögonblickets — demon påstår aldrig att den mäter nu.
    const r = D.inspections.infra_status[(body || {}).object_id];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/infrastructure/due") return D.inspections.infra_due;
  if (path === "/v1/infrastructure/sla") {
    // Endast demons standardkombination är bakad; frysta åldrar gör
    // varje annan kombination till en gissning — som vägras.
    const b = body || {};
    if (b.promised_minutes !== 240 || b.window_hours !== 168)
      throw new Error(DEMOFEL);
    return D.inspections.infra_sla;
  }
  if (path.startsWith("/v1/sponsorship/stats")) {
    const r = D.sponsorship.stats[qp(path, "campaign_id")];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/sponsorship") return D.sponsorship.overview;
  if (path === "/v1/sponsorship/mission") {
    const r = D.sponsorship.mission[(body || {}).campaign_id];
    if (!r) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/connections" && !body) return D.krypin.connections;
  if (path === "/v1/company" && !body) return D.krypin.company;
  // Ingen logga bakad i demon — ärligt tom i stället för hittepå.
  // Uppladdning/borttagning är SKRIVNINGAR och faller igenom till
  // DEMOFEL, samma regel som routines/assets ovan.
  if (path === "/v1/company/logo" && !body) return { logo: null };
  if (path === "/v1/staff" && !body) return D.krypin.staff;
  if (path === "/v1/credentials") return D.krypin.credentials;
  // Leveransloggen är ärligt tom i den statiska demon (kundens egna
  // rader finns inte här); en omkörning eller ett larmschema är en
  // SKRIVNING och vägras — men GET-ytorna svarar med sina tomma,
  // korrekt formade svar i stället för att falla igenom till DEMOFEL.
  // path bär querystrengen (?limit=25), så matchningen är på PREFIX —
  // samma mönster som /v1/mrai och /v1/analysis ovan — och den mer
  // specifika /streaks-ytan prövas FÖRE den allmänna /deliveries.
  if (path.startsWith("/v1/deliveries/streaks")) return {streaks: []};
  if (path.startsWith("/v1/deliveries") && !body) return D.krypin.deliveries;
  if (path === "/v1/pushes") return D.pushes_catalog;
  if (path === "/v1/pushes/preview") {
    const r = D.pushes_preview[`${(body || {}).dataset}:${(body || {}).format}`];
    if (!r) throw new Error(DEMOFEL);
    if (r.refused_en) throw new Error(r.refused_en);
    return r;
  }
  if (path.startsWith("/v1/surface")) return D.surface;
  if (path.startsWith("/v1/chain")) return D.chain;
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
    if fragment:
        # En artefaktsida wrappas i sitt eget dokumentskelett vid
        # publicering, så egna <html>/<head>/<body> skulle nästlas. Plocka
        # ut innehållet i stället för att låta två skelett krocka.
        import re as _re
        huvud = _re.search(r"<head[^>]*>(.*?)</head>", html, _re.S)
        kropp = _re.search(r"<body[^>]*>(.*?)</body>", html, _re.S)
        if not (huvud and kropp):
            raise SystemExit("hittade inte head/body — fragmentet vore trasigt")
        html = huvud.group(1).strip() + "\n" + kropp.group(1).strip()

    out = pathlib.Path(out_path)
    out.write_text(html, encoding="utf-8")
    print(f"demo: {out} ({round(out.stat().st_size / 1024)} kB) · "
          f"{len(demo['ask'])} frågor · {len(demo['scans'])} svep · "
          f"{len(demo['wf_maps'])} kartor · {len(demo['forecasts'])} prognoser · "
          f"{len(demo['gaps'])} gap-analyser")


if __name__ == "__main__":
    _argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    build(_argv[0] if _argv else "landvex-demo.html",
          lite="--lite" in sys.argv, fragment="--fragment" in sys.argv)
