"""Kostnad/nytta – förväntat värde bortom känslorna ("what does the data say").

När ett beslut ställer en KOSTNAD mot en osäker VINNING – vad ett skydd
kostar mot vad det kan ge, vad en offentlig satsning kostar mot den handel/
turism den kan dra in – ska svaret komma ur flödena, inte ur affekt. Det här
lagret räknar förväntat värde ärligt och grindat:

  * `expected_value(costs, benefits)` – säkra utflöden mot sannolikhets-
    vägda vinningar. Ger nettovärde, nytto/kostnads-kvot (BCR), och
    BREAK-EVEN-SANNOLIKHETEN: vid vilken samlad sannolikhet slutar det löna
    sig? En fråga, inte en dom.
  * `sensitivity` – vilken enskild post svänger utfallet mest? Var är
    slutsatsen skör?
  * Grindat som scenario-lagret: räcker inte antalet TROVÄRDIGA KÄLLOR
    (`MIN_SOURCES`) → `insufficient_basis` (vi spekulerar inte). Poster utan
    källa räknas, men redovisas som osäkra i data_coverage.

Aldrig ett råd ("du bör"), aldrig kausalitet. Förväntat värde är EN inramning,
betingad av de belopp, sannolikheter och källor som valts – framing_disclosure
följer alltid med. Rent stdlib.
"""
from __future__ import annotations

from .integrity import framing_disclosure

MIN_SOURCES = 2

CAVEAT = ("Expected value is one framing of cost against uncertain gain — not "
          "advice and not a claim about what will happen. It is contingent on "
          "the amounts, probabilities and sources chosen; change an input and "
          "the sign can change (see sensitivity).")


def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _norm_items(items: list[dict], *, is_benefit: bool) -> list[dict]:
    out = []
    for it in items or []:
        amount = _num(it.get("amount"))
        prob = _num(it.get("probability", 1.0), 1.0) if is_benefit else 1.0
        prob = min(1.0, max(0.0, prob))
        out.append({"label": str(it.get("label", "item")),
                    "amount": amount, "probability": prob,
                    "source": str(it.get("source", "")),
                    "expected": round(amount * prob, 6)})
    return out


def _sources(costs: list[dict], benefits: list[dict]) -> list[str]:
    return sorted({it["source"] for it in (costs + benefits) if it["source"]})


def expected_value(costs: list[dict], benefits: list[dict], *,
                   horizon_years: int = 1, decision: str = "",
                   currency: str = "USD") -> dict:
    """Väg säkra kostnader mot sannolikhetsvägda vinningar.

    costs: [{label, amount, source?}] – utflöden (probability ignoreras, 1.0).
    benefits: [{label, amount, probability(0-1, default 1), source?}].
    Grindat på MIN_SOURCES trovärdiga källor. Se modulens docstring.
    """
    C = _norm_items(costs, is_benefit=False)
    B = _norm_items(benefits, is_benefit=True)
    srcs = _sources(C, B)
    n_items = len(C) + len(B)
    sourced = sum(1 for it in (C + B) if it["source"])
    coverage = round(sourced / n_items, 4) if n_items else 0.0

    if len(srcs) < MIN_SOURCES:
        return {"status": "insufficient_basis", "decision": decision,
                "n_sources": len(srcs), "needed": MIN_SOURCES,
                "data_coverage": coverage,
                "caveat": "We do not speculate: fewer than "
                          f"{MIN_SOURCES} credible sources back these flows.",
                "framing": framing_disclosure({"basis": "insufficient",
                                               "sourced_share": coverage})}

    total_cost = round(sum(it["amount"] for it in C), 6)
    gross_benefit = round(sum(it["amount"] for it in B), 6)
    expected_benefit = round(sum(it["expected"] for it in B), 6)
    net = round(expected_benefit - total_cost, 6)
    bcr = round(expected_benefit / total_cost, 4) if total_cost > 0 else None
    # Break-even: vilken enhetlig skalning av vinnings-sannolikheterna gör
    # netto = 0? p* = total_cost / gross_benefit (mängderna oförändrade).
    break_even_p = (round(total_cost / gross_benefit, 4)
                    if gross_benefit > 0 else None)
    if break_even_p is None:
        be_note = "no positive gain specified — cannot break even"
    elif break_even_p > 1:
        be_note = ("even at certainty the stated gains do not cover the cost "
                   f"(needs {break_even_p:.2f}× the specified upside)")
    else:
        be_note = (f"breaks even once the combined gain probability reaches "
                   f"{break_even_p:.0%}")

    lean = ("favorable" if net > 0 else "unfavorable" if net < 0 else "neutral")

    return {
        "status": "assessed", "decision": decision, "currency": currency,
        "horizon_years": int(horizon_years),
        "total_cost": total_cost, "gross_benefit": gross_benefit,
        "expected_benefit": expected_benefit, "net_expected_value": net,
        "benefit_cost_ratio": bcr,
        "break_even_probability": break_even_p, "break_even_note": be_note,
        # "leans", aldrig "är" – en riktning, inte en dom.
        "leans": lean,
        "sensitivity": sensitivity(C, B),
        "basis": {"n_sources": len(srcs), "sources": srcs,
                  "items": len(C) + len(B), "sourced_items": sourced,
                  "data_coverage": coverage},
        "costs": C, "benefits": B,
        "caveat": CAVEAT,
        "framing": framing_disclosure(
            {"amounts": "as supplied", "probabilities": "as supplied",
             "n_sources": len(srcs), "sourced_share": coverage,
             "method": "expected value = Σ(gain·p) − Σcost",
             "not_advice": True, "not_causal": True}),
    }


def sensitivity(costs: list[dict], benefits: list[dict]) -> dict:
    """Vilken post svänger nettot mest? En-i-taget bidrag till |netto|.

    För varje post: dess expected-bidrag och andel av det totala absoluta
    flödet – störst andel = där slutsatsen är skörast. Ren beskrivning.
    """
    rows = []
    for it in costs:
        rows.append({"label": it["label"], "kind": "cost",
                     "impact": round(-it["amount"], 6)})
    for it in benefits:
        rows.append({"label": it["label"], "kind": "benefit",
                     "impact": round(it["expected"], 6)})
    total_abs = sum(abs(r["impact"]) for r in rows) or 1.0
    for r in rows:
        r["share_of_swing"] = round(abs(r["impact"]) / total_abs, 4)
    rows.sort(key=lambda r: -r["share_of_swing"])
    top = rows[0]["label"] if rows else None
    return {"drivers": rows, "most_decisive": top,
            "note": "share_of_swing ranks where the conclusion is most "
                    "fragile — the largest share moves the net the most."}
