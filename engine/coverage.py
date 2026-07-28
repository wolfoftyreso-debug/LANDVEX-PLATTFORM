"""Vad vi kan svara på HÄR — och vad vi inte kan.

Hela alt-data-branschen döljer att den är enkelkällad. Att publicera sin
egen täckning är därför inte en svaghet utan en kil: ingen konkurrent gör
det, och kunden som frågar "vad bygger det här på i Texas?" får ett svar
i stället för en broschyr.

Ingenting här är nytt påstått. Allt räknas ur tillstånd plattformen redan
bär: signalkatalogen, vertikalernas vikter, adaptrarnas räckvidd och
anslutningsläge, sensorklasserna och marknadens kalibreringsflagga.

**Det centrala talet är `real_weight`** — hur stor andel av en bransch
VIKTADE signalbild som en verklig, ansluten källa faktiskt kan svara för
på den här marknaden. Inte "hur många signaler finns" (39 överallt, och
lika meningslöst överallt), utan hur mycket av det som avgör svaret som
vilar på något annat än en deterministisk simulering.

För USA är talet 0,0 i skrivande stund. Det är obekvämt och det är sant,
och det är precis den siffran en köpare ska få se innan hon frågar efter
den — inte efter.

En källa som är ansluten räknas bara för de marknader den FAKTISKT kan
svara för (`DataSource.markets`). SCB-adaptern är kopplad och `/health`
säger "ok", men den kan inte svara för en punkt i Texas.

Rent stdlib.
"""
from __future__ import annotations

from engine.markets import DEFAULT_MARKET, MARKETS
from engine.signals import CATALOG
from engine.verticals import VERTICALS

# Bandet för hur mycket av svaret som vilar på verklig data. Samma
# fyrgradiga logik som kartlegenden, men om VÅRT underlag — aldrig om
# hur säkert ett enskilt svar är. Det omdömet bor i corroboration.py och
# vägrar med flit att bli en procentsats.
_BANDS = ((0.60, "substantial", "Most of what drives the answer here is "
                                "real, sourced data."),
          (0.30, "partial", "A meaningful part of the answer rests on real "
                            "data; the rest is simulated and labelled."),
          (0.01, "thin", "Almost everything that drives the answer here is "
                         "simulated. Useful for shape and comparison, not "
                         "for a number you act on alone."),
          (0.0, "none", "No connected source can answer for this market "
                        "yet. Every signal falls back to the deterministic "
                        "mock, which is labelled as such in every "
                        "response."))


def _band(andel: float) -> tuple[str, str]:
    for grans, namn, text in _BANDS:
        if andel >= grans:
            return namn, text
    return _BANDS[-1][1], _BANDS[-1][2]


def _sources_for(market: str, sources=None) -> list:
    """Källorna som gäller för EN marknad, med anslutningsläge."""
    if sources is None:
        from engine.datasources.adapters import production_sources
        sources = production_sources()
    ut = []
    for s in sources:
        scope = tuple(getattr(s, "markets", ()) or ())
        ut.append({
            "source": s.name,
            "signals": tuple(getattr(s, "SIGNALS", ()) or ()),
            # Räckvidd: tom tuple = ingen geografisk gräns i adaptern.
            "covers_market": (not scope) or market in scope,
            "market_scope": list(scope) or ["any"],
            "connected": bool(getattr(s, "connected", True)),
        })
    return ut


def _signal_state(market: str, sources) -> dict[str, dict]:
    """Per signal: vem skulle svara här, och i vilket läge."""
    ut = {}
    for sid in CATALOG:
        rad = {"signal_id": sid, "label_en": CATALOG[sid].label_en,
               "state": "mock_only", "source": "mock", "would_be": ""}
        for s in sources:
            if sid not in s["signals"]:
                continue
            if not s["covers_market"]:
                # En adapter som finns men inte når hit är INTE samma sak
                # som ingen adapter: det ena är ett avtal, det andra en
                # ny integration.
                if rad["state"] == "mock_only":
                    rad["would_be"] = s["source"]
                    rad["state"] = "out_of_scope"
                continue
            if s["connected"]:
                rad.update({"state": "live", "source": s["source"],
                            "would_be": s["source"]})
                break
            rad.update({"state": "adapter_ready", "would_be": s["source"]})
        ut[sid] = rad
    return ut


def _vertical_rows(lage: dict) -> list[dict]:
    """Andel av varje branschs VIKTADE signalbild som en riktig källa bär."""
    rader = []
    for vid, v in VERTICALS.items():
        total = 0.0
        verklig = 0.0
        redo = 0.0
        for f in v.factors:
            for sid, sw in f.signals:
                w = f.weight * sw
                total += w
                st = lage.get(sid, {}).get("state")
                if st == "live":
                    verklig += w
                elif st in ("adapter_ready", "out_of_scope"):
                    redo += w
        andel = round(verklig / total, 3) if total else 0.0
        namn, _ = _band(andel)
        rader.append({
            "vertical_id": vid, "label_en": v.label_en,
            "real_weight": andel,
            "reachable_weight": round((verklig + redo) / total, 3)
            if total else 0.0,
            "band": namn,
        })
    rader.sort(key=lambda r: (-r["real_weight"], r["vertical_id"]))
    return rader


def _what_would_change_it(lage: dict, sources) -> list[dict]:
    """Konkret: vilken källa öppnar hur många signaler här."""
    per: dict[str, list[str]] = {}
    for sid, rad in lage.items():
        if rad["state"] in ("adapter_ready", "out_of_scope") \
                and rad["would_be"]:
            per.setdefault(rad["would_be"], []).append(sid)
    scope = {s["source"]: s for s in sources}
    ut = []
    for namn, sids in sorted(per.items(), key=lambda kv: -len(kv[1])):
        s = scope.get(namn, {})
        i_rackvidd = s.get("covers_market", True)
        ut.append({
            "source": namn, "opens_signals": sorted(sids),
            "count": len(sids),
            "what_en": ("Connect it — the adapter is written and reaches "
                        "this market."
                        if i_rackvidd else
                        f"Does NOT reach this market: the adapter is "
                        f"scoped to {', '.join(s.get('market_scope', []))}. "
                        f"A local equivalent has to be written; connecting "
                        f"this one changes nothing here."),
            "in_scope": i_rackvidd,
        })
    return ut


def _switchable(market: str) -> dict:
    """Nyckellösa källor som skulle höja täckningen här."""
    from engine.harvest import SOURCES, open_data_on, switchable_today

    rader = [r for r in switchable_today()
             if not SOURCES[r["source"]]["markets"]
             or market in SOURCES[r["source"]]["markets"]]
    av = [r for r in rader if not r["active"]]
    return {
        "sources": rader, "count": len(rader),
        "not_yet_on": [r["source"] for r in av],
        "switch_en": ("LANDVEX_OPEN_DATA=on turns on every keyless source "
                      "at once; each also has its own variable. Sources "
                      "that need a key are never enabled by it."),
        "open_data_on": open_data_on(),
        "cannot_en": ("Switching a source on does not make it answer. It "
                      "has to be harvested (make harvest) before the "
                      "request path has anything to read, and a harvest "
                      "that reached nobody stores nothing."),
    }


def coverage(market: str = "", *, sources=None) -> dict:
    """Täckningsytan för en marknad. Publik med flit."""
    mid = (market or DEFAULT_MARKET).lower()
    if mid not in MARKETS:
        raise ValueError(f"Unknown market: {mid}. "
                         f"Available: {', '.join(sorted(MARKETS))}")
    m = MARKETS[mid]
    kallor = _sources_for(mid, sources)
    lage = _signal_state(mid, kallor)

    antal = {"live": 0, "adapter_ready": 0, "out_of_scope": 0,
             "mock_only": 0}
    for rad in lage.values():
        antal[rad["state"]] += 1
    vertikaler = _vertical_rows(lage)
    snitt = (round(sum(v["real_weight"] for v in vertikaler)
                   / len(vertikaler), 3) if vertikaler else 0.0)
    namn, bandtext = _band(snitt)

    return {
        "market": mid, "market_label_en": m.label_en,
        "regions": len(m.regions),
        "economics_calibrated": bool(m.calibrated),
        "real_weight": snitt, "band": namn, "band_en": bandtext,
        "signals": {"total": len(lage), **antal},
        "signal_rows": sorted(lage.values(), key=lambda r: r["signal_id"]),
        "by_vertical": vertikaler,
        "what_would_change_it": _what_would_change_it(lage, kallor),
        # Vad som går att slå på NU, utan att ansöka om någonting. Det är
        # den fråga hela täckningsytan ställdes för att besvara: inte
        # bara "vad saknas" utan "vad kan jag göra åt det i dag".
        "switchable_today": _switchable(mid),
        "sources": kallor,
        "means_en": (
            "real_weight is the share of the WEIGHTED signal picture that "
            "a connected source can answer for here — not how many "
            "signals exist. Two markets with the same signal catalogue "
            "can differ completely, and this is the number that shows it."),
        "cannot_en": (
            "This says what the answer rests on, not whether an individual "
            "answer is right. How well a specific claim is corroborated is "
            "a separate judgement, expressed as a band and deliberately "
            "never as a percentage."),
        "honesty_en": (
            "Published on purpose. The alt-data segment hides "
            "single-sourcing; a customer who has to ask what a number "
            "rests on has already been given the wrong product."),
    }


def compare_markets(markets: list[str] | None = None, *,
                    sources=None) -> dict:
    """Samma tal för flera marknader — det ärliga svaret på 'täcker ni X?'."""
    ids = [m.lower() for m in (markets or sorted(MARKETS))]
    rader = []
    for mid in ids:
        if mid not in MARKETS:
            continue
        c = coverage(mid, sources=sources)
        rader.append({k: c[k] for k in
                      ("market", "market_label_en", "regions",
                       "economics_calibrated", "real_weight", "band")})
    rader.sort(key=lambda r: (-r["real_weight"], r["market"]))
    med = [r for r in rader if r["real_weight"] > 0]
    return {
        "markets": rader, "count": len(rader),
        "with_real_data": len(med),
        "summary_en": (
            f"{len(med)} of {len(rader)} market(s) have any connected "
            f"source at all. The rest run on the deterministic mock, "
            f"which is labelled as such in every response."),
        "cannot_en": (
            "A market with real data in one signal is not a covered "
            "market. Read real_weight, not the presence of a source."),
    }
