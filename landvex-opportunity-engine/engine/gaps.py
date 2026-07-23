"""Gap Analysis Engine – hittar obalanser, inte bara efterfrågan.

Det verkliga värdet ligger inte i "var är efterfrågan hög?" utan i
"var är efterfrågan hög, utbudet lågt OCH utvecklingen på väg upp?"
– den outnyttjade marknaden. Typexemplet: stort fordonsunderlag, ingen
verkstad i närheten, växande flotta och hög köpkraft.

Tre axlar per region, alla ur vertikalens egen signalbild:

  EFTERFRÅGAN (D)  viktat normaliserat värde av vertikalens
                   efterfrågesignaler (allt utom konkurrenssignaler)
  UTBUDSUNDERSKOTT (U)  konkurrenssignalerna – högt värde = få/svaga
                   aktörer i förhållande till efterfrågan
  UTVECKLING (M)   samma momentumsignaler som beslutskorten

  obalans = 100 × (0.45·D + 0.35·U + 0.20·M)     (dokumenterad vikt)
  klass   = stark_obalans om D ≥ 0.6, U ≥ 0.6 och M ≥ 50
            annars potentiell (score ≥ 55) eller svag

Samma motor för alla vertikaler – bilverkstad, tandläkare, förskola:
det enda som skiljer är vilka signaler som driver efterfrågan, och det
äger vertikalprofilen redan. Målgrupper utöver entreprenören: kedjor
som planerar återförsäljarnät, banker, fastighetsägare och kommuner –
samma analys, samma datalager.
"""
from __future__ import annotations

from typing import Any

from .datasources.base import Resolver
from .markets import get_market, plural_region_label
from .models import Location
from .scan import momentum_of
from .scoring import analyze
from .signals import CATALOG
from .verticals import VERTICALS

_SUPPLY_SIGNALS = ("competition_pressure", "provider_gap")

_STRENGTH_SV = ((0.8, "very strong"), (0.6, "strong"), (0.4, "moderate"),
                (0.2, "weak"), (0.0, "very weak"))
_SUPPLY_SV = ((0.8, "very low competition"), (0.6, "low competition"),
              (0.4, "balanced competition"), (0.2, "high competition"),
              (0.0, "saturated market"))


def _grade(n: float, table) -> str:
    return next(label for lo, label in table if n >= lo)


def _axes(report, vertical_id: str) -> tuple[float, float, list, list]:
    """(D, U, efterfrågerader, utbudsrader) ur rapportens signalbild."""
    d_num = d_den = u_num = u_den = 0.0
    d_rows, u_rows = [], []
    for f in VERTICALS[vertical_id].factors:
        for sid, w in f.signals:
            s = report.signals.get(sid)
            if s is None:
                continue
            weight = f.weight * w
            n = s["normalized"]
            row = {"signal_id": sid, "label_en": CATALOG[sid].label_en,
                   "varde": s["value"], "enhet": CATALOG[sid].unit,
                   "kalla": s["source"]}
            if sid in _SUPPLY_SIGNALS:
                u_num += weight * n
                u_den += weight
                u_rows.append({**row, "bedomning_en": _grade(n, _SUPPLY_SV)})
            else:
                d_num += weight * n
                d_den += weight
                d_rows.append({**row, "n": n,
                               "bedomning_en": _grade(n, _STRENGTH_SV)})
    d_rows.sort(key=lambda r: -r.pop("n"))
    return (d_num / d_den if d_den else 0.5,
            u_num / u_den if u_den else 0.5, d_rows, u_rows)


def gap_analysis(vertical_id: str, market: str = "se",
                 resolver: Resolver | None = None,
                 top_n: int = 5) -> dict[str, Any]:
    """Rankar marknadens regioner efter obalans för en vertikal."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical_id}. "
                         f"Available: {', '.join(sorted(VERTICALS))}")
    mkt = get_market(market)

    entries = []
    for code, name, lat, lon in mkt.regions:
        report = analyze(Location(lat, lon, address=name), vertical_id,
                         resolver=resolver)
        d, u, d_rows, u_rows = _axes(report, vertical_id)
        mom = momentum_of(report)
        m01 = mom["value"] / 100.0
        score = round(100 * (0.45 * d + 0.35 * u + 0.20 * m01), 0)
        if d >= 0.6 and u >= 0.6 and mom["value"] >= 50:
            klass = "stark_obalans"
        elif score >= 55:
            klass = "potentiell_obalans"
        else:
            klass = "svag_obalans"
        entries.append({
            "kommun": name, "kommun_kod": code, "lat": lat, "lon": lon,
            "obalans_score": score, "klass": klass,
            "efterfragan": round(100 * d), "utbudsunderskott": round(100 * u),
            "utveckling": mom["value"], "utveckling_riktning": mom["direction"],
            "opportunity_score": report.opportunity_score,
            "data_coverage": report.data_coverage,
            "forklaring": {"efterfragan": d_rows[:6], "utbud": u_rows},
            "narrativ_en": (
                f"{name}: demand {round(100 * d)}/100, "
                f"supply deficit {round(100 * u)}/100, development "
                f"{mom['value']}/100 ({mom['direction']}). "
                + ("Classic imbalance – high demand, low supply, "
                   "positive development." if klass == "stark_obalans" else
                   "Partial imbalance – see the breakdown." if klass ==
                   "potentiell_obalans" else
                   "No clear imbalance at present.")),
        })
    entries.sort(key=lambda e: (-e["obalans_score"], e["kommun_kod"]))

    starka = sum(1 for e in entries if e["klass"] == "stark_obalans")
    return {
        "vertical_id": vertical_id,
        "vertical_label_en": VERTICALS[vertical_id].label_en,
        "market": mkt.id, "market_label_en": mkt.label_en,
        "bbox": list(mkt.bbox),
        "obalanser": entries[:top_n],
        "heatmap": [{"kommun": e["kommun"], "kommun_kod": e["kommun_kod"],
                     "lat": e["lat"], "lon": e["lon"],
                     "score": e["obalans_score"],
                     "band": ("gron" if e["klass"] == "stark_obalans" else
                              "gul" if e["klass"] == "potentiell_obalans"
                              else "rod")} for e in entries],
        "sammanfattning_en": (
            f"{starka} of {len(entries)} analyzed "
            f"{plural_region_label(mkt.region_label_en)} show strong "
            f"imbalance for {VERTICALS[vertical_id].label_en.lower()}."),
        "caveats_en": [
            "The imbalance formula (0.45·demand + 0.35·supply deficit + "
            "0.20·development) is a documented heuristic.",
            "The supply picture builds on the competition signals – real "
            "competitor data (the Places adapter) improves precision.",
        ],
    }
