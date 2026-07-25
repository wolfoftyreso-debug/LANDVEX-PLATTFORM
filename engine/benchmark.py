"""Benchmark mot jämförbara enheter – "är det på riktigt sant?".

För påståenden som "det är för få parkeringsplatser i Örebro sett till
jobben" är rätt fråga inte en känsla utan: räkna kvoten, jämför mot
JÄMFÖRBARA städer, och se om enheten är en avvikare eller ligger i
normalspannet. Systemet påstår inget – det placerar värdet i sin fördelning
med percentil, z-score och ett neutralt utlåtande, med källorna och
inramningen synliga.

Rent stdlib, bygger på `engine.stats`.
"""
from __future__ import annotations

from .integrity import framing_disclosure
from .stats import mean, percentile_rank, pstdev


def benchmark(value: float, peers: list[float], *, label: str = "unit",
              metric: str = "ratio", higher_is_better: bool | None = None,
              sources: list | None = None) -> dict:
    """Placera `value` i fördelningen av `peers` (jämförbara enheter).

    Returnerar percentil, z-score, band (low_outlier/below/normal/above/
    high_outlier) och ett neutralt utlåtande om huruvida ett påstått
    över-/underskott stöds av jämförelsedatan. Inget partiskt ord.
    """
    if len(peers) < 3:
        return {"status": "insufficient_peers", "n_peers": len(peers),
                "note": "Need ≥3 comparable units to benchmark honestly.",
                "framing": framing_disclosure({"basis": "too few peers"})}
    m, sd = mean(peers), pstdev(peers)
    pct = percentile_rank(value, peers)
    z = round((value - m) / sd, 4) if sd else 0.0
    if pct <= 5:
        band = "low_outlier"
    elif pct < 25:
        band = "below_typical"
    elif pct <= 75:
        band = "normal"
    elif pct < 95:
        band = "above_typical"
    else:
        band = "high_outlier"
    is_outlier = band in ("low_outlier", "high_outlier")
    verdict = (f"{label} sits at the {pct:.0f}th percentile of {len(peers)} "
               f"comparable units — "
               + ("an outlier; the claim of being unusual is supported by the data."
                  if is_outlier else
                  "within the normal range; a claim of being unusual is NOT "
                  "supported by the peer data."))
    return {
        "status": "benchmarked", "label": label, "metric": metric,
        "value": value, "n_peers": len(peers),
        "peer_mean": round(m, 4), "peer_median": round(sorted(peers)[len(peers) // 2], 4),
        "percentile": round(pct, 2), "zscore": z, "band": band,
        "is_outlier": is_outlier,
        "higher_is_better": higher_is_better,
        "verdict": verdict,
        "sources": list(sources or []),
        "caveat": ("Comparison to peers only. Whether the peer set is truly "
                   "comparable is itself a choice; a normal ratio is not proof "
                   "of adequacy, only of typicality."),
        "framing": framing_disclosure(
            {"peer_set_size": len(peers), "metric": metric,
             "note": "percentile depends entirely on which peers were chosen"}),
    }
