"""Jämförelsemodul – ställ 2–4 platser mot varandra för samma vertikal.

Typfrågan: "Vi står mellan lokalen på Hornsgatan och den i Solna –
vilken är bäst för vår frisörsalong?" Återanvänder analyze() rakt av;
modulen är ren presentation/aggregering ovanpå motorn och ärver därmed
determinism, datatäckning och narrativ.
"""
from __future__ import annotations

from typing import Any

from .datasources.base import Resolver
from .models import Location
from .risk import assess
from .scoring import analyze
from .verticals import VERTICALS


def compare(locations: list[dict[str, Any]], vertical_id: str,
            resolver: Resolver | None = None) -> dict[str, Any]:
    """locations: [{lat, lon, address?, radius_minutes?}, ...] (2–4 st)."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Okänd vertikal: {vertical_id}. "
                         f"Tillgängliga: {', '.join(sorted(VERTICALS))}")
    if not 2 <= len(locations) <= 4:
        raise ValueError("Jämförelsen kräver 2–4 platser.")

    locs, reports, risks = [], [], []
    for i, d in enumerate(locations):
        try:
            loc = Location(lat=float(d["lat"]), lon=float(d["lon"]),
                           address=str(d.get("address", f"Plats {i + 1}")),
                           radius_minutes=int(d.get("radius_minutes", 10)))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Plats {i + 1}: lat och lon krävs som tal.")
        locs.append(loc)
        reports.append(analyze(loc, vertical_id, resolver=resolver))
        risks.append(assess(loc, vertical_id, resolver=resolver))

    names = [l.address for l in locs]

    # Faktormatris: rad per faktor, kolumn per plats, vinnare markerad.
    matrix = []
    for fi, spec in enumerate(VERTICALS[vertical_id].factors):
        scores = [r.factors[fi].score for r in reports]
        best = max(range(len(scores)), key=lambda i: (scores[i], -i))
        matrix.append({
            "factor_id": spec.id, "label_sv": spec.label_sv,
            "weight": spec.weight, "scores": scores, "vinnare_index": best,
            "narrativ_sv": [r.factors[fi].narrative_sv for r in reports],
        })

    totals = [r.opportunity_score for r in reports]
    order = sorted(range(len(totals)),
                   key=lambda i: (-totals[i], risks[i]["total_risk"]))
    win, second = order[0], order[1]
    margin = totals[win] - totals[second]

    if margin >= 8:
        rek = (f"{names[win]} är tydligt starkast "
               f"({int(totals[win])} mot {int(totals[second])}).")
    elif margin >= 3:
        rek = (f"{names[win]} leder knappt ({int(totals[win])} mot "
               f"{int(totals[second])}) – väg in risk och hyresvillkor.")
    else:
        rek = (f"Jämnt lopp mellan {names[win]} och {names[second]} "
               f"(±{int(margin)} poäng) – låt riskprofil, "
               f"lokalkostnad och magkänsla avgöra.")

    return {
        "vertical_id": vertical_id,
        "vertical_label_sv": VERTICALS[vertical_id].label_sv,
        "platser": [{
            "index": i, "address": names[i],
            "lat": locs[i].lat, "lon": locs[i].lon,
            "opportunity_score": totals[i],
            "risk_total": risks[i]["total_risk"],
            "risk_band": risks[i]["band"],
            "data_coverage": reports[i].data_coverage,
            "insikter_sv": reports[i].insights_sv,
        } for i in range(len(locs))],
        "faktormatris": matrix,
        "vinnare_index": win,
        "marginal": round(margin, 0),
        "rekommendation_sv": rek,
        "caveats_sv": reports[win].caveats_sv,
    }
