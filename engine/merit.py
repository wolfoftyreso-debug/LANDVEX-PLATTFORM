"""Meritmotorn – var går det MÄTBART bra, och på vilka grunder?

Plattformen har hittills varit bra på att avslöja svaga antaganden. Det är
halva uppdraget. Den andra halvan: **framgång ska premieras på exakt samma
bevisregler**. Ett system som bara letar fel blir ett anklagelsemaskineri;
ett som bara berömmer blir en broschyr. Samma måttstock åt båda hållen är
det som gör någon av bedömningarna trovärdig.

Symmetrin är därför inbyggd och utskriven i svaret (`same_standard_en`):
    * samma normalisering och percentiler som riskbedömningen
    * samma krav på jämförelsegrupp innan ett omdöme alls ges
    * samma källmärkning per drivare – uppskattat visas som uppskattat
    * samma förbud mot kausalitet: motorn säger vad som är mätbart
      ANNORLUNDA, aldrig VARFÖR någon lyckades

Sex dimensioner av näringslivsförmåga, alla byggda av befintliga signaler:

    enterprise      företagstäthet och nyföretagande
    labour          arbetskraftsdeltagande och utbildningsresultat
    diversification bredd i näringslivet (inte beroende av en enda sektor)
    conversion      infrastrukturinvestering som faktiskt blir byggd
    attraction      inflyttning och att folk har råd att bo kvar
    resilience      energi- och uppkopplingsberedskap

"Hur" = de dimensioner kommunen faktiskt leder på, med råvärden och källa.
"Varför" = de starkaste drivarna, uttryckligen som skillnader, inte orsaker.

Rent stdlib.
"""
from __future__ import annotations

from .integrity import framing_disclosure
from .signals import CATALOG, normalize
from .stats import mean, percentile_rank

# dimension → (etikett, förklaring, ((signal, vikt), …))
DIMENSIONS: dict[str, dict] = {
    "enterprise": {
        "label_en": "Enterprise base",
        "means_en": "How much business activity the place actually carries "
                    "per resident, and whether it is growing.",
        "signals": (("business_density", 0.6), ("pop_growth_pct", 0.4))},
    "labour": {
        "label_en": "Labour engagement",
        "means_en": "How much of the working-age population is in work, and "
                    "the skills base underneath it.",
        "signals": (("labor_participation", 0.6), ("education_outcomes", 0.4))},
    "diversification": {
        "label_en": "Economic breadth",
        "means_en": "Whether activity spans several sectors rather than "
                    "resting on one employer or industry.",
        "signals": (("business_density", 0.3), ("office_workers", 0.3),
                    ("tourism_index", 0.2), ("logistics_access", 0.2))},
    "conversion": {
        "label_en": "Investment conversion",
        "means_en": "Whether infrastructure spending turns into permits and "
                    "actual building — plans becoming things.",
        "signals": (("building_permits", 0.5), ("infra_invest", 0.3),
                    ("detail_plans", 0.2))},
    "attraction": {
        "label_en": "Attraction & retention",
        "means_en": "People moving in, and still being able to afford to "
                    "stay.",
        "signals": (("pop_growth_pct", 0.5), ("housing_affordability", 0.3),
                    ("life_satisfaction", 0.2))},
    "resilience": {
        "label_en": "Operating resilience",
        "means_en": "The energy and connectivity base a business needs to "
                    "keep running.",
        "signals": (("energy_resilience", 0.5),
                    ("digital_connectivity", 0.5))},
}

MIN_PEERS = 5
MIN_COVERAGE = 0.5          # under detta uttalar sig motorn inte
LEAD_PERCENTILE = 70.0      # att "leda" på en dimension


def _norm(signal_id: str, value) -> float | None:
    d = CATALOG.get(signal_id)
    if d is None or value is None:
        return None
    return normalize(d, value)


def dimension_scores(signals: dict) -> dict:
    """Poäng 0–100 per dimension + hur stor del av underlaget som fanns."""
    out = {}
    for did, spec in DIMENSIONS.items():
        parts, weights, used, srcs = [], [], [], set()
        for sid, w in spec["signals"]:
            row = signals.get(sid) or {}
            n = _norm(sid, row.get("value") if isinstance(row, dict) else row)
            if n is None:
                continue
            parts.append(n * w)
            weights.append(w)
            used.append({"signal_id": sid,
                         "label_en": (CATALOG[sid].label_en
                                      if hasattr(CATALOG[sid], "label_en")
                                      else sid),
                         "value": row.get("value") if isinstance(row, dict) else row,
                         "normalized": round(n, 4),
                         "source": (row.get("source")
                                    if isinstance(row, dict) else None)})
            if isinstance(row, dict) and row.get("source"):
                srcs.add(row["source"])
        wsum = sum(weights)
        out[did] = {
            "dimension": did, "label_en": spec["label_en"],
            "means_en": spec["means_en"],
            "score": round(sum(parts) / wsum * 100, 2) if wsum else None,
            "coverage": round(wsum / sum(w for _, w in spec["signals"]), 4),
            "drivers": used, "sources": sorted(srcs),
        }
    return out


def merit(region_code: str, region_name: str, signals: dict,
          peer_scores: dict[str, list[float]] | None = None) -> dict:
    """Näringslivsförmåga för en plats – med hur och varför, aldrig varför-så.

    peer_scores: {dimension: [poäng i jämförbara regioner]} för percentiler.
    """
    dims = dimension_scores(signals)
    scored = [d for d in dims.values() if d["score"] is not None]
    coverage = round(mean([d["coverage"] for d in dims.values()]), 4) \
        if dims else 0.0

    if not scored or coverage < MIN_COVERAGE:
        return {"region": region_name, "region_code": region_code,
                "status": "insufficient_basis", "coverage": coverage,
                "reason_en": (f"Only {coverage:.0%} of the underlying signals "
                              f"are available — not enough to judge a place "
                              f"either way."),
                "framing": framing_disclosure({"basis": "insufficient"})}

    overall = round(mean([d["score"] for d in scored]), 2)
    peer_scores = peer_scores or {}
    for d in dims.values():
        peers = peer_scores.get(d["dimension"]) or []
        if d["score"] is not None and len(peers) >= MIN_PEERS:
            d["percentile"] = round(percentile_rank(d["score"], peers), 1)
            d["leads"] = d["percentile"] >= LEAD_PERCENTILE
        else:
            d["percentile"] = None
            d["leads"] = None

    leads = [d for d in dims.values() if d.get("leads")]
    leads.sort(key=lambda d: -(d["percentile"] or 0))
    lags = [d for d in dims.values()
            if d.get("percentile") is not None and d["percentile"] < 30]

    # "Varför" = de starkast normaliserade drivarna bakom det den leder på.
    why = []
    for d in leads[:3]:
        for drv in sorted(d["drivers"], key=lambda x: -x["normalized"])[:2]:
            why.append({"dimension": d["dimension"],
                        "label_en": drv["label_en"],
                        "value": drv["value"], "source": drv["source"],
                        "normalized": drv["normalized"]})

    return {
        "region": region_name, "region_code": region_code, "status": "assessed",
        "overall": overall, "coverage": coverage,
        "dimensions": list(dims.values()),
        "leads_on": [{"dimension": d["dimension"], "label_en": d["label_en"],
                      "score": d["score"], "percentile": d["percentile"],
                      "means_en": d["means_en"]} for d in leads],
        "lags_on": [{"dimension": d["dimension"], "label_en": d["label_en"],
                     "score": d["score"], "percentile": d["percentile"]}
                    for d in lags],
        "how_en": (
            f"{region_name} leads on "
            + ", ".join(d["label_en"].lower() for d in leads)
            + f" ({len(leads)} of {len(DIMENSIONS)} dimensions)."
            if leads else
            f"{region_name} does not lead its comparison group on any "
            f"dimension — that is a finding, not an omission."),
        "why_en": ("What is measurably different: "
                   + "; ".join(f"{w['label_en']} {w['value']}" for w in why)
                   if why else
                   "Nothing stands out strongly enough to name."),
        "drivers": why,
        # Kärnan: samma måttstock åt båda hållen.
        "same_standard_en": (
            "Credit here is awarded on exactly the standard used to "
            "challenge a place: the same normalisation, the same peer "
            "percentiles, the same source labelling on every driver, and the "
            "same refusal to answer when coverage is thin. What is not "
            "claimed is causation — these are measurable differences, not "
            "reasons for success."),
        "framing": framing_disclosure({
            "measure": "six dimensions of business performance",
            "comparison": "percentile against peer regions",
            "not_causal": True, "coverage": coverage}),
    }


def rank(regions: list[dict], top_n: int = 10) -> dict:
    """Rangordna platser på näringslivsförmåga – merit, inte tyckande.

    regions: [{"code","name","signals"}]. Bygger peer-fördelningen ur
    materialet självt, så varje plats jämförs med de övriga.
    """
    prepared = [(r, dimension_scores(r.get("signals") or {}))
                for r in regions]
    peer_scores: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for _, dims in prepared:
        for did, d in dims.items():
            if d["score"] is not None:
                peer_scores[did].append(d["score"])

    rows = []
    for r, _ in prepared:
        m = merit(r.get("code", ""), r.get("name", ""), r.get("signals") or {},
                  peer_scores=peer_scores)
        if m["status"] == "assessed":
            rows.append(m)
    rows.sort(key=lambda m: -m["overall"])
    for i, m in enumerate(rows, 1):
        m["rank"] = i
    return {"ranking": rows[:top_n], "assessed": len(rows),
            "of_regions": len(regions),
            "dimensions": [{"id": k, "label_en": v["label_en"],
                            "means_en": v["means_en"]}
                           for k, v in DIMENSIONS.items()],
            "note_en": "Ranked on measurable performance against each other, "
                       "with every driver sourced. The same engine that "
                       "flags weak assumptions awards this credit — one "
                       "standard, both directions.",
            "framing": framing_disclosure({"ranked_against": "each other",
                                           "not_causal": True})}
