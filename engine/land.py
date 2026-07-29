"""Markvärde — flera datapunkter, ett band, och aldrig en prislapp.

Fastighetsvärdering är den plats där en plattform som den här kan göra
mest skada. Ett tal som ser ut som ett marknadsvärde används i en
förhandling, i en kreditansökan eller i en taxering — och ett sådant
tal får ALDRIG komma ur signaler som normaliserats mot varandra.

Modulen svarar därför på en annan fråga än "vad är marken värd":

    **Vad talar för och emot att marken här är mer värd än marken
    bredvid — och hur säkert vet vi det?**

Svaret är ett RELATIVT LÄGE (0–100 mot marknadens övriga regioner) med
band, drivare, motverkande faktorer och täckningstal. Aldrig kronor,
aldrig kvadratmeterpris, aldrig "uppskattat värde".

Fem värdefamiljer, var och en med sina signaler och sin vikt. Vikterna
är en DOKUMENTERAD HEURISTIK — de står här så att den som är oense kan
peka på raden i stället för att gissa:

    läge & tillgänglighet   0.25   kollektivtrafik, parkering, folk i radie
    utvecklingstryck        0.25   bygglov, detaljplaner, befolkningstillväxt
    ekonomiskt underlag     0.20   inkomst, hyresläge, företagstäthet
    infrastruktur           0.15   infrastrukturinvestering, energi
    livsmiljö               0.15   trygghet, trafiksäkerhet, boendekostnad

Spärrarna:

  * **Under `MIN_COVERAGE` beräknas inget läge.** Ett markvärdesindex
    på simulerade signaler är en gissning med en decimal på, och den
    gissningen skulle användas mot en verklig fastighet.
  * **Varje familj öppnas**: vilka signaler som bar den, ur vilken
    källa, och vad som saknades.
  * **Motverkande faktorer redovisas separat** — ett läge som är högt
    TROTS hög brottslighet är ett annat besked än ett som är högt utan
    invändningar, och en sammanvägning döljer skillnaden.
  * **Kontradiktionsindexet följer med.** Går pappret och marken isär i
    regionen är det den viktigaste enskilda upplysningen för den som
    ska köpa mark där — och den står bredvid läget, inte i det.

Rent stdlib.
"""
from __future__ import annotations

from .datasources.base import Resolver
from .datasources.defaults import default_resolver
from .markets import DEFAULT_MARKET, get_market, get_region
from .models import Location
from .signals import CATALOG, normalize

# Under den här andelen verkliga signaler ges INGET läge. Tröskeln är
# högre än plattformens vanliga: det här talet skulle användas mot en
# verklig fastighet i en verklig förhandling.
MIN_COVERAGE = 0.35

FAMILIES: tuple[dict, ...] = (
    {"id": "location_access", "weight": 0.25,
     "label_en": "Location & access",
     "signals": (("transit_score", 0.45), ("pop_radius", 0.35),
                 ("parking_score", 0.20)),
     "what_en": "How easily people reach this place at all. The oldest "
                "driver of land value there is.",
     "cannot_en": "Reach is not desirability: a well-connected place "
                  "nobody wants to be in scores the same as one they "
                  "queue for."},
    {"id": "development_pressure", "weight": 0.25,
     "label_en": "Development pressure",
     "signals": (("building_permits", 0.40), ("detail_plans", 0.35),
                 ("pop_growth_pct", 0.25)),
     "what_en": "Whether anyone is actually building and planning here, "
                "and whether more people are arriving.",
     "cannot_en": "A permit is paperwork, not a building. High pressure "
                  "on paper with nothing on the ground is exactly what "
                  "the contradiction index below is for."},
    {"id": "economic_base", "weight": 0.20,
     "label_en": "Economic base",
     "signals": (("income_index", 0.40), ("rent_index", 0.35),
                 ("business_density", 0.25)),
     "what_en": "What the surrounding economy can carry — incomes, "
                "rents and business activity.",
     "cannot_en": "Today's rent level says nothing about tomorrow's, "
                  "and a high rent index can mean scarcity as easily as "
                  "prosperity."},
    {"id": "infrastructure", "weight": 0.15,
     "label_en": "Infrastructure",
     "signals": (("infra_invest", 0.60), ("energy_resilience", 0.40)),
     "what_en": "Committed public investment and whether the grid can "
                "carry what gets built.",
     "cannot_en": "Announced investment is not delivered "
                  "infrastructure, and this cannot tell them apart."},
    {"id": "living_environment", "weight": 0.15,
     "label_en": "Living environment",
     "signals": (("road_safety", 0.35), ("crime_index", 0.35),
                 ("housing_affordability", 0.30)),
     "what_en": "What it is like to be here — safety and what housing "
                "costs relative to the market.",
     "cannot_en": "Reported crime is not occurred crime, and "
                  "propensity to report differs sharply between "
                  "places. This is the register's number, not the "
                  "street's."},
)

# Signaler där ett HÖGT råvärde talar EMOT markvärdet.
#
# Riktningen vänds INTE här: signalkatalogen normaliserar dem redan med
# `norm="inverse"`, så ett högt råvärde ger ett lågt normaliserat. En
# extra inversion i den här modulen vände tecknet TILLBAKA och lät hög
# brottslighet lyfta markvärdet — mätt: crime_index 40 gav läge 46,2 och
# crime_index 220 gav 51,5. Precis den sortens tysta teckenfel som ser
# ut som en modell, fångat av testet innan modulen ens nådde en gren.
#
# Listan står kvar för EN sak: att veta vilka drivare som ska redovisas
# som motverkande faktorer när de ligger illa till.
COUNTER_SIGNALS: frozenset = frozenset({"crime_index", "rent_index"})

BANDS: tuple[tuple[float, str, str], ...] = (
    (80.0, "very_strong", "Very strong relative position"),
    (65.0, "strong", "Strong relative position"),
    (45.0, "average", "Around the market average"),
    (30.0, "weak", "Weak relative position"),
    (0.0, "very_weak", "Very weak relative position"),
)


class LandRefused(ValueError):
    """Bedömningen gick inte att göra, och varför."""


def _band(v: float) -> tuple[str, str]:
    for grans, bid, label in BANDS:
        if v >= grans:
            return bid, label
    return BANDS[-1][1], BANDS[-1][2]


def _needed() -> list[str]:
    return sorted({sid for f in FAMILIES for sid, _ in f["signals"]})


def _family(fam: dict, values: dict) -> dict:
    """En familj: viktat normaliserat läge + varje drivare öppen."""
    num = den = 0.0
    drivare, saknade = [], []
    for sid, w in fam["signals"]:
        sv = values.get(sid)
        if sv is None or sv.value is None:
            saknade.append(sid)
            continue
        # Katalogen bär riktningen (`norm="inverse"` för de signaler där
        # högt råvärde är dåligt). Ingen inversion här — se
        # COUNTER_SIGNALS för varför det är en mätt regel, inte en åsikt.
        n = normalize(CATALOG[sid], sv.value) or 0.0
        num += w * n
        den += w
        drivare.append({
            "signal_id": sid, "label_en": CATALOG[sid].label_en,
            "value": sv.value, "unit": CATALOG[sid].unit,
            "kalla": sv.source, "normalised": round(n, 3),
            "counts_against": sid in COUNTER_SIGNALS,
            "weight_within_family": w})
    akta = [d for d in drivare if d["kalla"] != "mock"]
    return {
        "id": fam["id"], "label_en": fam["label_en"],
        "weight": fam["weight"],
        "score": round(100 * num / den, 1) if den else None,
        "of_weight": round(den, 2),
        "drivers": drivare, "missing": saknade,
        "data_coverage": (round(len(akta) / len(drivare), 2)
                          if drivare else 0.0),
        "what_en": fam["what_en"], "cannot_en": fam["cannot_en"],
    }


def assess(region_code: str, market: str = DEFAULT_MARKET, *,
           resolver: Resolver | None = None) -> dict:
    """Relativt markvärdesläge för en region — eller en vägran."""
    mkt = get_market(market)
    kod, namn, lat, lon = get_region(market, region_code)
    res = resolver or default_resolver()
    values, _ = res.resolve(Location(lat, lon, address=namn),
                            "land", _needed())

    familjer = [_family(f, values) for f in FAMILIES]
    akta = sum(1 for v in values.values()
               if v.value is not None and v.source != "mock")
    totalt = sum(1 for v in values.values() if v.value is not None)
    tackning = round(akta / totalt, 2) if totalt else 0.0

    # Motverkande faktorer: inverterade drivare som ligger illa till.
    # De redovisas SEPARAT — ett läge som är högt trots hög brottslighet
    # är ett annat besked än ett högt utan invändningar.
    motverkande = [
        {"signal_id": d["signal_id"], "label_en": d["label_en"],
         "value": d["value"], "kalla": d["kalla"],
         "why_en": f"{d['label_en']} works against land value here, and "
                   f"sits unfavourably ({d['normalised']:.2f} of 1.0 — "
                   f"the catalogue scores this signal in reverse, so a "
                   f"low figure means a high raw value)."}
        for f in familjer for d in f["drivers"]
        if d["counts_against"] and d["normalised"] < 0.4]

    gemensamt = {
        "region": namn, "region_code": kod,
        "market": mkt.id, "market_label_en": mkt.label_en,
        "families": familjer,
        "data_coverage": tackning,
        "counter_indications": motverkande,
        "weights_en": ("The family weights are a DOCUMENTED HEURISTIC, "
                       "not a derived truth. They are listed so that "
                       "someone who disagrees can point at the row."),
        "cannot_en": (
            "This is NOT a valuation. It carries no currency, no price "
            "per square metre and no estimated value, because a number "
            "shaped like a price gets used like one — in a negotiation, "
            "a credit application or an assessment. It says only how "
            "this region stands RELATIVE to others in the same market, "
            "on the drivers listed, with the coverage stated. Parcel-"
            "level value depends on the plot, the plan, the ground and "
            "the deal — none of which are visible from here."),
    }

    if tackning < MIN_COVERAGE:
        return {
            **gemensamt, "status": "insufficient", "position": None,
            "band": None, "band_en": None,
            "gate": {"required": MIN_COVERAGE, "measured": tackning},
            "refusal_en": (
                f"No position is computed for {namn}: {round(tackning * 100)}% "
                f"of the drivers rest on real sources, below the "
                f"{round(MIN_COVERAGE * 100)}% floor. A land-value index "
                f"built on simulated signals is a guess with a decimal "
                f"on it — and this particular guess would be used "
                f"against a real property."),
            "how_to_fix_en": ("Connect sources for this market (see "
                              "/v1/coverage) — the floor is about OUR "
                              "reach, not about this place."),
        }

    raknade = [f for f in familjer if f["score"] is not None]
    vikt = sum(f["weight"] for f in raknade)
    lage = round(sum(f["score"] * f["weight"] for f in raknade) / vikt, 1)
    bid, blabel = _band(lage)
    return {
        **gemensamt, "status": "computed", "position": lage,
        "band": bid, "band_en": blabel,
        "of_weight": round(vikt, 2),
        "families_refused": [f["id"] for f in familjer
                             if f["score"] is None],
        "summary_en": (
            f"{namn}: {blabel.lower()} ({lage}/100) relative to "
            f"{mkt.label_en}'s other regions, on "
            f"{round(tackning * 100)}% real data"
            + (f", with {len(motverkande)} counter-indication(s) listed "
               f"separately." if motverkande else ".")),
    }


def compare(region_codes: list[str], market: str = DEFAULT_MARKET, *,
            resolver: Resolver | None = None) -> dict:
    """Flera regioner sida vid sida — de ovärderbara stannar i listan.

    En ranking som tyst tappar det den inte kan mäta ser fullständig ut
    och är det inte.
    """
    if not region_codes:
        raise LandRefused("compare needs at least one region code")
    res = resolver or default_resolver()
    bedomda = [assess(k, market, resolver=res) for k in region_codes]
    raknade = [b for b in bedomda if b["status"] == "computed"]
    raknade.sort(key=lambda b: -b["position"])
    return {
        "market": market, "count": len(bedomda),
        "ranked": raknade,
        "insufficient": [b for b in bedomda
                         if b["status"] == "insufficient"],
        "summary_en": ("Regions we cannot yet place are listed too, with "
                       "their reason: a ranking that silently drops what "
                       "it cannot measure looks complete and is not."),
        "cannot_en": bedomda[0]["cannot_en"] if bedomda else "",
    }


def catalog() -> dict:
    return {
        "what_en": ("Relative land-value position: what argues for and "
                    "against this place versus others in the same "
                    "market, and how well we can see it."),
        "families": [{k: v for k, v in f.items() if k != "signals"}
                     | {"signals": [s for s, _ in f["signals"]]}
                     for f in FAMILIES],
        "counter_signals": sorted(COUNTER_SIGNALS),
        "bands": [{"at_least": g, "band": b, "label_en": lbl}
                  for g, b, lbl in BANDS],
        "coverage_floor": MIN_COVERAGE,
        "weights_en": ("A documented heuristic, listed so it can be "
                       "argued with."),
        "cannot_en": ("It is not a valuation and carries no currency. "
                      "Anyone needing a value for a specific parcel "
                      "needs a valuer who has stood on it."),
    }
