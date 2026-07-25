"""Känsliga kategorier – till ytan, men som sanning, inte som vapen.

Brottsoffer, födelseland/etnicitet, hälsa, religion, sexualitet: legitima
statistiska ämnen (BRÅ, ONS, SCB publicerar dem) – och exakt de ämnen där
naiv statistik gör mest skada. Det som skiljer en trovärdig källa från en
pamflett är inte att man tiger, utan att man:

  1. SKYDDAR SMÅ GRUPPER – k-anonymitet, minsta cellstorlek (annars
     re-identifiering + brus). En grupp under `MIN_CELL` får inte redovisas.
  2. KRÄVER CONFOUNDER-KONTROLL – ett rått samband mellan ett skyddat
     attribut och ett utfall är meningslöst tills man håller ålder, inkomst
     och urbanisering konstant. Grinden VÄGRAR utan deklarerade confounders
     och visar om sambandet ÖVERLEVER kontrollen (`partial`).
  3. FÖRBJUDER KAUSALITET & GENERALISERING – aldrig "grupp X orsakar Y";
     varning för ekologiskt felslut (aggregat ≠ individ).
  4. KRÄVER OFFICIELLA KÄLLOR – annars inget svar.

Rent stdlib, bygger på `engine.correlate` + `engine.integrity`.
"""
from __future__ import annotations

from .correlate import cross_domain, partial_correlation
from .integrity import framing_disclosure

# Skyddade kategorier (utökas som data).
SENSITIVE_CATEGORIES = {
    "origin": "country of birth / ethnicity",
    "victim_status": "victims of crime (e.g. sexual violence)",
    "health": "health status / diagnosis",
    "religion": "religion or belief",
    "sexuality": "sexual orientation",
    "disability": "disability",
    "gender": "gender",
}
MIN_CELL = 10        # k-anonymitet: minsta cell som får redovisas
MIN_SOURCES = 2

ECOLOGICAL = ("Ecological fallacy: this is an aggregate/area-level "
              "association and says nothing about any individual. An "
              "aggregate pattern must never be read as a property of a person.")
CONFOUND = ("Protected-attribute associations are especially confounded. A "
            "raw gap often shrinks or vanishes once age, income, employment "
            "and urbanisation are controlled — always read the partial value.")


def guard(category: str, group_sizes: list[int], confounders: list,
          sources: list) -> dict:
    """Släpper igenom ett känsligt attribut endast med alla skyddsåtgärder.

    Returnerar {allowed, reasons}. reasons tomt ⇒ tillåtet.
    """
    reasons = []
    if category in SENSITIVE_CATEGORIES:
        small = [n for n in group_sizes if n < MIN_CELL]
        if small:
            reasons.append(f"group(s) below k-anonymity floor {MIN_CELL} "
                           f"(sizes {small}) — cannot be shown")
        if not confounders:
            reasons.append("no confounders declared — a protected-attribute "
                           "association requires controlling for age/income/"
                           "urbanisation before it may be shown")
    if len(sources) < MIN_SOURCES:
        reasons.append(f"only {len(sources)} sources (need ≥ {MIN_SOURCES}, "
                       f"official statistics for sensitive categories)")
    return {"allowed": not reasons, "reasons": reasons}


def sensitive_association(a: list[float], b: list[float], control: list[float],
                          *, category: str, group_sizes: list[int],
                          sources: list, confounders: list,
                          label_a: str = "attribute", label_b: str = "outcome",
                          label_c: str = "confounder") -> dict:
    """Ett känsligt samband, bara med alla grindar passerade.

    Visar RÅTT samband bredvid det CONFOUNDER-KONTROLLERADE (partial), så att
    frågan "överlever sambandet när man kontrollerar för de självklara
    faktorerna?" besvaras – vilket är hela skillnaden mot en pamflett.
    """
    g = guard(category, group_sizes, confounders, sources)
    if not g["allowed"]:
        return {"status": "refused", "category": category,
                "reasons": g["reasons"],
                "note": "Everything to the surface — but only with the "
                        "safeguards that make it truth, not ammunition.",
                "framing": framing_disclosure({"blocked_by": "sensitive-guard"})}
    raw = cross_domain(a, b, label_a=label_a, label_b=label_b)
    part = partial_correlation(a, b, control, label_a=label_a,
                               label_b=label_b, label_c=label_c)
    raw_r, part_r = raw["pearson"], part["partial"]
    # Teckenvändning = Simpsons paradox: den råa riktningen är vilseledande.
    sign_flip = (raw_r > 0) != (part_r > 0) and abs(raw_r) > 0.1 and abs(part_r) > 0.1
    survived = (abs(part_r) >= 0.2 and not part["confounder_suspected"]
                and not sign_flip)
    if sign_flip:
        reading = (f"Raw association {raw_r:+.2f} REVERSES to {part_r:+.2f} when "
                   f"controlling for {', '.join(confounders)} — Simpson's "
                   f"paradox; the raw direction is misleading.")
    elif survived:
        reading = (f"Raw association {raw_r:+.2f}; controlling for "
                   f"{', '.join(confounders)} it stays {part_r:+.2f} — it largely persists.")
    else:
        reading = (f"Raw association {raw_r:+.2f}; controlling for "
                   f"{', '.join(confounders)} it becomes {part_r:+.2f} — it "
                   f"largely disappears, i.e. the raw gap is mostly explained by "
                   f"the controlled factors, not the attribute.")
    return {
        "status": "shown_with_safeguards", "category": category,
        "category_meaning": SENSITIVE_CATEGORIES.get(category, category),
        "raw_association": raw_r,
        "controlled_association": part_r,
        "controlled_for": confounders,
        "survives_controls": survived,
        "sign_reversal": sign_flip,
        "reading": reading,
        "k_anonymity": {"min_cell": MIN_CELL, "group_sizes": group_sizes,
                        "ok": True},
        "sources": sources,
        "warnings": [ECOLOGICAL, CONFOUND],
        "caveat": raw["caveat"],
        "framing": framing_disclosure(
            {"category": category, "controlled_for": confounders,
             "note": "association after controls, not causation; aggregate not "
                     "individual"}),
    }
