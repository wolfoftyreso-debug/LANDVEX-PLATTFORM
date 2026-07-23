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

from engine.ask import ask
from engine.markets import MARKETS, market_catalog
from engine.models import Location
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
]
# Bakade svep (marknad, vertikal) och prognosyrken per marknad.
SCANS = [("se", "frisor"), ("se", "cafe"), ("se", "vvs"), ("se", "gym"),
         ("se", "bilverkstad"), ("de", "vvs"), ("us", "restaurang")]
FORECAST_OCC = {"se": ["elektriker", "vvs_montor", "sjukskoterska",
                       "larare", "snickare", "forskollarare"],
                "de": ["elektriker"], "us": ["sjukskoterska"]}


def _strip(f: dict) -> dict:
    f = dict(f)
    f["prognoser"] = [{k: v for k, v in p.items() if k != "bana"}
                      for p in f["prognoser"]]
    return f


def build(out_path: str) -> None:
    demo: dict = {
        "options": {**profile_options(), "scan_levels": SCAN_LEVEL_OPTIONS},
        "occupations": occupation_catalog(),
        "markets": market_catalog(),
        "ask": {q: ask(q) for q in FRAGOR},
        "scans": {}, "wf_maps": {}, "forecasts": {}, "simulate": {},
        "risk": {},
    }
    for market, vid in SCANS:
        res = scan(profile_from_dict({"vertical_id": vid}), top_n=5,
                   market=market)
        demo["scans"][f"{market}:{vid}"] = res
        for h in res["hotspots"]:
            key = f"{h['lat']:.3f}:{h['lon']:.3f}:{vid}"
            demo["risk"][key] = assess(
                Location(h["lat"], h["lon"], address=h["lage_sv"]), vid)
    for occ in OCCUPATIONS:
        demo["wf_maps"][f"se:{occ}"] = national_map(occ, 2035)
    demo["wf_maps"]["de:elektriker"] = national_map("elektriker", 2035,
                                                    market="de")
    demo["wf_maps"]["us:sjukskoterska"] = national_map("sjukskoterska", 2035,
                                                       market="us")
    for market, occs in FORECAST_OCC.items():
        for occ in occs:
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
  const res = await fetch(path, body
    ? { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) }
    : undefined);
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
    if (!r) throw new Error("Demosvep finns för: " +
      Object.keys(D.scans).join(", ") + ". " + DEMOFEL);
    return r;
  }
  if (path.startsWith("/v1/workforce/map")) {
    const r = D.wf_maps[`${qp(path, "market") || "se"}:${qp(path, "occupation_id")}`];
    if (!r || qp(path, "target_year") !== "2035")
      throw new Error("Demokartor: alla yrken i Sverige, elektriker i Tyskland, sjuksköterska i USA – målår 2035. " + DEMOFEL);
    return r;
  }
  if (path === "/v1/workforce/forecast") {
    const r = D.forecasts[`${body.market || "se"}:${body.kommun_kod}:${(body.occupation_ids || [])[0]}`];
    if (!r || body.target_year !== 2035) throw new Error(DEMOFEL);
    return r;
  }
  if (path === "/v1/workforce/simulate") {
    const r = D.simulate[`${body.market || "se"}:${body.kommun_kod}:${body.occupation_id}`];
    if (!r || body.extra_places_per_year !== 30)
      throw new Error("Demon simulerar exakt 30 platser/år. " + DEMOFEL);
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
          f"{len(demo['wf_maps'])} kartor · {len(demo['forecasts'])} prognoser")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "landvex-demo.html")
