"""Marknadsmättnad – "hur pass mättad är marknaden för X i Y?"

En enkel fråga med ett svårt svar. Mättnad är inte antalet företag, utan
antalet företag i förhållande till underlaget – och i förhållande till hur
tätt det ligger på jämförbara platser. Tre led, alla redovisade:

    1. UTBUD   antal arbetsställen i branschen (helst ur registret)
    2. NORMERING  per 10 000 invånare, så en storstad kan jämföras med en
       förort
    3. JÄMFÖRELSE  mot samma tal i jämförbara kommuner → percentil och band

Bandet säger vad det säger och inget mer:
    underserved   påtagligt glesare än jämförbara platser
    room          något glesare
    balanced      i linje med jämförelsegruppen
    tight         tätare än de flesta
    saturated     påtagligt tätare

**Mättnad är inte samma sak som att det saknas plats.** En gles marknad kan
vara gles för att efterfrågan saknas; en tät kan bära fler för att
efterfrågan är stark. Därför redovisas efterfrågesidan bredvid – och svaret
säger uttryckligen att det är ett underlag att utmana, inte ett besked.

Kritiskt för trovärdigheten: `measured` visar om utbudssiffran kommer ur ett
officiellt register eller är en uppskattning ur signalbilden. En uppskattad
siffra presenteras aldrig som en registeruppgift.

Rent stdlib.
"""
from __future__ import annotations

from .integrity import framing_disclosure
from .registers import REGISTERS, RegisterClient, industry_code
from .stats import percentile_rank

# Band efter percentil i jämförelsegruppen (täthet per 10 000 invånare).
BANDS: tuple[tuple[float, str, str], ...] = (
    (10.0, "underserved", "Markedly sparser than comparable places."),
    (30.0, "room", "Somewhat sparser than comparable places."),
    (70.0, "balanced", "In line with the comparison group."),
    (90.0, "tight", "Denser than most comparable places."),
    (100.1, "saturated", "Markedly denser than comparable places."),
)

MIN_PEERS = 5          # under detta är en percentil inte meningsfull
PER_CAPITA_BASE = 10_000


def band_for(percentile: float) -> tuple[str, str]:
    for cutoff, band, text in BANDS:
        if percentile < cutoff:
            return band, text
    return BANDS[-1][1], BANDS[-1][2]


def _density(count: float, population: float) -> float | None:
    if not population or population <= 0:
        return None
    return round(count / population * PER_CAPITA_BASE, 4)


def saturation(vertical: str, region_code: str, region_name: str, *,
               population: float, supply: dict, peers: list[dict],
               country: str = "se", demand_index: float | None = None) -> dict:
    """Hur mättad marknaden är för `vertical` i en region.

    supply: {"count": n, "measured": bool, "source": str, "year": int}
      – measured=True endast när talet kommer ur ett officiellt register.
    peers: [{"name","count","population"}] – jämförbara regioner.
    demand_index: valfritt efterfrågemått (0–100) för att sätta utbudet i
      relation till underlaget; utelämnas hellre än gissas.
    """
    count = supply.get("count")
    measured = bool(supply.get("measured"))
    density = _density(count, population) if count is not None else None

    peer_rows = []
    for p in peers:
        d = _density(p.get("count"), p.get("population"))
        if d is not None:
            peer_rows.append({"name": p.get("name", ""), "density": d,
                              "count": p.get("count"),
                              "population": p.get("population")})
    peer_densities = [p["density"] for p in peer_rows]

    code = industry_code(vertical, country)
    base = {
        "vertical": vertical, "region": region_name, "region_code": region_code,
        "country": country,
        "supply": {"establishments": count, "measured": measured,
                   "source": supply.get("source"), "year": supply.get("year"),
                   "basis_en": ("Official business register."
                                if measured else
                                "ESTIMATE derived from local signals — not a "
                                "register count. Connect the register to make "
                                "this figure real.")},
        "population": population,
        "density_per_10k": density,
        "industry_code": code,
        "register": (REGISTERS.get(country) or {}).get("name"),
    }

    if density is None or len(peer_densities) < MIN_PEERS:
        return {**base, "status": "insufficient_basis",
                "reasons": ([] if density is not None else
                            ["no supply count or population for this region"])
                + ([] if len(peer_densities) >= MIN_PEERS else
                   [f"only {len(peer_densities)} comparable regions "
                    f"(need >= {MIN_PEERS})"]),
                "verdict_en": "Not enough basis to say how saturated this "
                              "market is — the platform does not guess at it.",
                "framing": framing_disclosure({"basis": "insufficient"})}

    pct = round(percentile_rank(density, peer_densities + [density]), 1)
    band, band_text = band_for(pct)
    peer_median = sorted(peer_densities)[len(peer_densities) // 2]

    # Hur många fler/färre som skulle föra tätheten till gruppens median.
    at_median = peer_median * population / PER_CAPITA_BASE
    delta = round(at_median - count, 1) if count is not None else None

    verdict = (f"{region_name} has {count} {vertical} establishments — "
               f"{density:g} per 10,000 residents, which is the {pct:g}th "
               f"percentile of {len(peer_densities)} comparable places "
               f"({band}). {band_text}")

    out = {**base, "status": "assessed",
           "percentile": pct, "band": band, "band_en": band_text,
           "peer_median_density": round(peer_median, 4),
           "peers_compared": len(peer_densities),
           "peers": sorted(peer_rows, key=lambda r: -r["density"])[:10],
           "to_reach_peer_median": delta,
           "to_reach_peer_median_en": (
               f"{abs(delta):.0f} {'fewer' if delta < 0 else 'more'} "
               f"establishments would put {region_name} at the peer median."
               if delta is not None else None),
           "verdict_en": verdict,
           "caveat_en": (
               "Density is not the same as opportunity. A sparse market may "
               "be sparse because demand is weak; a dense one may carry more "
               "because demand is strong. Read this together with the demand "
               "side, and treat it as a basis to challenge — not a verdict."),
           "framing": framing_disclosure({
               "measure": "establishments per 10,000 residents",
               "comparison_group": f"{len(peer_densities)} regions",
               "supply_measured": measured,
               "not_a_verdict": True})}

    if demand_index is not None:
        out["demand_index"] = demand_index
        # Enkel, förklarbar läsning: tät marknad + svag efterfrågan är något
        # annat än tät marknad + stark efterfrågan.
        if band in ("tight", "saturated") and demand_index >= 60:
            read = ("Dense, but demand is strong — density alone does not "
                    "close the door.")
        elif band in ("tight", "saturated"):
            read = "Dense and demand is not strong. The hardest combination."
        elif band in ("underserved", "room") and demand_index >= 60:
            read = ("Sparse while demand is strong — the combination worth "
                    "examining first.")
        else:
            read = ("Sparse, but so is demand. Thin supply here is not "
                    "automatically an opening.")
        out["demand_reading_en"] = read
    return out


def estimate_supply(competition_pressure: float | None,
                    population: float, vertical: str) -> dict:
    """Uppskattat utbud när registret inte är anslutet – TYDLIGT märkt.

    Härleds ur konkurrenstryckssignalen (0–10) skalad mot befolkningen. Det
    är en uppskattning för att kedjan ska gå att köra, aldrig ett påstående
    om hur många företag som finns. `measured` är alltid False.
    """
    if competition_pressure is None or not population:
        return {"count": None, "measured": False, "source": None}
    per_10k = max(0.0, float(competition_pressure)) * 0.9
    return {"count": int(round(per_10k * population / PER_CAPITA_BASE)),
            "measured": False, "source": "estimated from local signals",
            "year": None}


def supply_for(vertical: str, country: str, region_code: str, *,
               population: float, competition_pressure: float | None = None,
               client: RegisterClient | None = None) -> dict:
    """Registret först, uppskattning som ärlig fallback."""
    client = client or RegisterClient()
    real = client.establishments(country, region_code, vertical)
    if real is not None:
        return real
    return estimate_supply(competition_pressure, population, vertical)
