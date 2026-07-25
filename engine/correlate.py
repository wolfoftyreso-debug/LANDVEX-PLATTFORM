"""Tvärdomän-korrelation – kost × läkemedel × levnad, ärligt byggt.

Det här lagret finns för att göra rätt sak i exakt den domän där naiva
korrelationer är farligast. Det SURFAR samband som hypoteser och VÄGRAR
kalla dem orsak. Fyra försvar mot siffrans falska auktoritet:

1. Association, aldrig kausalitet. Varje svar bär en obligatorisk caveat och
   inramning (`integrity.framing_disclosure`) – "statistik ljuger alltid".
2. Skenkorrelations-flagga: starkt |r| på litet n märks som misstänkt.
3. Confounder-kontroll: `partial_correlation` visar om sambandet ÖVERLEVER
   när man håller en tredje variabel konstant (den ärliga uppgraderingen).
4. Replikering över marknader: `cross_market` visar om samma samband gäller
   i flera OBEROENDE länder just nu – det som skiljer en signal från brus.

Rent stdlib, bygger på `engine.stats`. Inga medicinska/politiska slutsatser
– bara mätbara samband med sin osäkerhet och sina val redovisade.
"""
from __future__ import annotations

import math

from .integrity import framing_disclosure
from .stats import lag_correlation, mean, pearson, spearman

CAVEAT = ("Observed association only. This is NOT causation: confounders are "
          "unaccounted unless controlled for, and a correlation can arise from "
          "a shared third cause, selection, or chance. Use as a hypothesis to "
          "investigate, never as a claim.")


def confidence_tier(r: float, n: int) -> str:
    """Konfidensnivå ur |r| och n via t-statistik. Aldrig 'signifikant' på
    för lite data. Nivåer: high (n≥30,p<0.01) / medium (n≥15,p<0.05) /
    low (n≥10,p<0.1) / not_significant / insufficient."""
    if n < 10:
        return "insufficient"
    if abs(r) >= 0.9999:
        return "high"
    t = abs(r) * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else math.inf
    if n >= 30 and t > 2.58:
        return "high"
    if n >= 15 and t > 1.96:
        return "medium"
    if n >= 10 and t > 1.66:
        return "low"
    return "not_significant"


def cross_domain(a: list[float], b: list[float], *, max_lag: int = 6,
                 label_a: str = "A", label_b: str = "B") -> dict:
    """Samband mellan två tidsserier/tvärsnitt (t.ex. kostmått × sjukdomstal).

    Returnerar Pearson + Spearman + bästa lag + konfidens + skenflagga +
    obligatorisk caveat och inramning. Aldrig ett kausalt ord.
    """
    n = min(len(a), len(b))
    r = pearson(a, b)
    rho = spearman(a, b)
    lag = lag_correlation(a, b, max_lag=max_lag)
    tier = confidence_tier(r, n)
    spurious = abs(r) > 0.8 and n < 20
    return {
        "pair": [label_a, label_b], "n": n,
        "pearson": r, "spearman": rho, "lag": lag,
        "confidence": tier, "spurious_warning": spurious,
        "direction": "positive" if r > 0 else "negative" if r < 0 else "none",
        "caveat": CAVEAT,
        "framing": framing_disclosure(
            {"n": n, "confounders_controlled": [], "measure": "pearson/spearman",
             "note": "association, not causation"}),
    }


def partial_correlation(a: list[float], b: list[float],
                        control: list[float], *, label_a: str = "A",
                        label_b: str = "B", label_c: str = "C") -> dict:
    """Delkorrelation: sambandet A–B när C hålls konstant.

    r_ab.c = (r_ab − r_ac·r_bc) / sqrt((1−r_ac²)(1−r_bc²)). Om sambandet
    kollapsar när man kontrollerar för C var C sannolikt en confounder –
    det ärliga steget innan man ens tänker ordet "orsak".
    """
    n = min(len(a), len(b), len(control))
    r_ab = pearson(a, b)
    r_ac = pearson(a, control)
    r_bc = pearson(b, control)
    denom = math.sqrt(max(0.0, (1 - r_ac ** 2) * (1 - r_bc ** 2)))
    r_partial = ((r_ab - r_ac * r_bc) / denom) if denom else 0.0
    r_partial = round(max(-1.0, min(1.0, r_partial)), 6)
    collapsed = abs(r_ab) - abs(r_partial) > 0.2
    return {
        "pair": [label_a, label_b], "controlled_for": label_c, "n": n,
        "pearson": r_ab, "partial": r_partial,
        "confidence": confidence_tier(r_partial, n),
        "confounder_suspected": collapsed,
        "interpretation": (f"Association {'largely disappears' if collapsed else 'persists'} "
                           f"when controlling for {label_c} — "
                           + ("{} likely explains it.".format(label_c) if collapsed
                              else "not explained by {} alone.".format(label_c))),
        "caveat": CAVEAT,
        "framing": framing_disclosure(
            {"n": n, "confounders_controlled": [label_c],
             "note": "partial correlation is still not causation"}),
    }


def cross_market(datasets: list[dict], *, label_a: str = "A",
                 label_b: str = "B") -> dict:
    """Replikering: samma A–B-samband över flera OBEROENDE marknader.

    datasets: [{market, a:[…], b:[…]}]. Rapporterar per marknad + ett
    aggregat: i hur många marknader sambandet är signifikant OCH samma
    tecken. Ett samband som håller i många länder samtidigt är starkare än
    ett – men fortfarande inte kausalt.
    """
    rows = []
    for d in datasets:
        res = cross_domain(d.get("a", []), d.get("b", []),
                           label_a=label_a, label_b=label_b)
        rows.append({"market": d.get("market", "?"), "n": res["n"],
                     "pearson": res["pearson"], "confidence": res["confidence"],
                     "direction": res["direction"],
                     "spurious_warning": res["spurious_warning"]})
    sig = [r for r in rows if r["confidence"] in ("high", "medium", "low")]
    pos = sum(1 for r in sig if r["direction"] == "positive")
    neg = sum(1 for r in sig if r["direction"] == "negative")
    dominant = "positive" if pos >= neg else "negative"
    agree = pos if dominant == "positive" else neg
    total = len(rows)
    consistency = round(agree / total, 4) if total else 0.0
    return {
        "pair": [label_a, label_b], "markets": rows,
        "n_markets": total, "n_significant": len(sig),
        "replication": {
            "holds_in": f"{agree}/{total} markets",
            "dominant_direction": dominant if sig else "none",
            "consistency": consistency},
        "verdict": ("Replicates across independent markets — a strong "
                    "hypothesis to investigate." if consistency >= 0.6 and len(sig) >= 3
                    else "Does not replicate consistently — treat with caution."),
        "caveat": CAVEAT,
        "framing": framing_disclosure(
            {"n_markets": total, "note": "replication strengthens a hypothesis, "
             "it does not establish cause; markets share global confounders too"}),
    }
