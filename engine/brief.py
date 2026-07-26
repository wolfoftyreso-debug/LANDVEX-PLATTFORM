"""Daily Brief – vad systemet hittade utan att någon frågade.

Steget från sökverktyg till bevakning: motorn arbetar kontinuerligt, och
det som har högt beslutsvärde publiceras utan att en fråga ställts först.

Fyra saker skiljer den här implementationen från den enkla varianten, och
alla fyra kommer ur plattformens egen doktrin:

1. **Observation, aldrig juridisk slutsats.** "Tecken på olovlig
   markanvändning" är inte en observation, det är en anklagelse — och den
   kräver kännedom om bygglovsstatus som en satellitbild inte har. Systemet
   rapporterar det den ser (*ytan har förändrats*) och avvikelsen mot
   registret (*inget motsvarande lov hittat*), aldrig domen. Det är
   dessutom mer användbart: den som ska agera behöver diskrepansen, inte
   ett omdöme. Varje rapport bär `does_not_establish_en`.

2. **Ingen påhittad konfidenssiffra.** "94 %" med två värdesiffror är
   precis den sortens tal parameterrevisionen underkände. Ingenting i
   plattformen är ännu kalibrerat mot utfall, så en procentsats vore
   falsk precision om något som låter som en sannolikhet. Konfidensen
   redovisas som ett BAND med sina beståndsdelar synliga och en not om
   att det inte är en kalibrerad sannolikhet. Den dagen utfallsmotorn har
   underlag kan bandet bytas mot ett kalibrerat tal.

3. **Alternativ, inte rekommendationer.** Systemet säger aldrig "skicka
   fältpersonal". Det listar vad man KAN göra och vad varje alternativ
   skulle avgöra — inklusive att låta bli. Beslutet, och utfallet, är
   människans.

4. **En tyst dag är ett giltigt svar.** En brief som måste fyllas börjar
   snart lyfta brus för att fylla den. Hittas inget som når tröskeln säger
   den det rakt ut.

Prioriteringen återanvänder `engine.worthiness` – den signifikansmodellen
finns redan och gör exakt det som efterfrågas. Två konkurrerande
rangordningsmodeller i samma system är en garanti för att de glider isär.

Rent stdlib.
"""
from __future__ import annotations

from .integrity import canonical_hash, framing_disclosure
from .offering import brief_scope as offering_brief_scope
from .worthiness import PRIORITY, worthiness

# ── Vad systemet får påstå att det sett ─────────────────────────────────
# observation = det sensorn/registret faktiskt visar
# never_en    = slutsatsen den observationen INTE bär
DETECTION_KINDS: dict[str, dict] = {
    "structure_change": {
        "label_en": "Change to a structure",
        "observation_en": "The built surface at this location differs from "
                          "the previous observation.",
        "never_en": "That the change is unpermitted. Permit status comes "
                    "from the building register, not from imagery.",
        "sectors": ("construction", "real_estate")},
    "new_activity": {
        "label_en": "Activity without a matching registration",
        "observation_en": "Activity is visible at a site with no "
                          "corresponding entry found in the business "
                          "register.",
        "never_en": "That the operator is acting illegally. A register can "
                    "lag, and the search may simply have missed it.",
        "sectors": ("commerce", "construction")},
    "traffic_shift": {
        "label_en": "Change in traffic flow",
        "observation_en": "Measured flow differs materially from the same "
                          "period previously.",
        "never_en": "The cause. A road closure, a new employer and a "
                    "counting fault all look the same here.",
        "sectors": ("transport", "infrastructure")},
    "land_use_change": {
        "label_en": "Change in land use",
        "observation_en": "Surface cover or use at this parcel differs from "
                          "the previous observation.",
        "never_en": "That the use is unlawful. That is a legal finding for "
                    "the authority holding the permit record — the platform "
                    "reports the discrepancy, not a verdict.",
        "sectors": ("real_estate", "forestry", "agriculture")},
    "energy_change": {
        "label_en": "Change around an energy installation",
        "observation_en": "Output, connection or footprint differs from the "
                          "expected pattern.",
        "never_en": "A safety judgement. Deviation is not the same as fault.",
        "sectors": ("energy", "infrastructure")},
    "infrastructure_decay": {
        "label_en": "Condition declining faster than comparable assets",
        "observation_en": "The condition indicator falls faster here than in "
                          "comparable assets over the same period.",
        "never_en": "That it is unsafe. Rate of change is not a structural "
                    "assessment.",
        "sectors": ("infrastructure", "transport")},
    "object_gone": {
        "label_en": "Object no longer observed",
        "observation_en": "An object present in earlier observations is "
                          "absent in the latest.",
        "never_en": "That it was removed unlawfully, or removed at all — "
                    "cloud, angle and season all hide things.",
        "sectors": ("real_estate", "infrastructure")},
    "object_new": {
        "label_en": "Object newly observed",
        "observation_en": "An object absent in earlier observations is "
                          "present in the latest.",
        "never_en": "When it appeared. Between two observations is the most "
                    "that can be said.",
        "sectors": ("construction", "real_estate")},
    "pattern_deviation": {
        "label_en": "Economic or spatial pattern off its history",
        "observation_en": "The measured pattern departs from its own "
                          "historical range.",
        "never_en": "That the departure is meaningful. A record is not a "
                    "cause, and a run of records is what randomness looks "
                    "like sometimes.",
        "sectors": ("economy", "real_estate")},
}

# ── Konfidens: beståndsdelar, aldrig en påhittad procentsats ────────────
CONFIDENCE_INPUTS = ("source_count", "sources_measured", "corroboration",
                     "history_points", "resolution")
CONFIDENCE_BANDS = ((0.75, "high"), (0.5, "moderate"), (0.25, "low"))

ACTION_OPTIONS: dict[str, str] = {
    "watch": "Keep it under observation and see whether it repeats. "
             "Resolves nothing now; costs nothing now.",
    "verify_desk": "Check the relevant register from the desk. Resolves "
                   "whether a record exists — not what is actually there.",
    "verify_field": "Send someone to look. Resolves what is actually there, "
                    "at the cost of a trip.",
    "ask_authority": "Ask the body that holds the permit or licence record. "
                     "Resolves the status question the platform cannot.",
    "none": "Do nothing. A legitimate choice, and the one most often right "
            "when confidence is low and impact is small.",
}


def confidence(inputs: dict) -> dict:
    """Konfidens som band + beståndsdelar. Aldrig en kalibrerad sannolikhet.

    inputs: source_count (int), sources_measured (int – hur många av dem som
    kommer ur en ansluten källa), corroboration (0–1, oberoende bekräftelse),
    history_points (int), resolution (0–1, hur fin upplösningen är).
    """
    n = max(0, int(inputs.get("source_count", 0)))
    measured = min(n, max(0, int(inputs.get("sources_measured", 0))))
    corr = min(1.0, max(0.0, float(inputs.get("corroboration", 0.0))))
    hist = max(0, int(inputs.get("history_points", 0)))
    res = min(1.0, max(0.0, float(inputs.get("resolution", 0.0))))

    parts = {
        "sources": round(min(1.0, n / 3.0) * 0.25, 4),
        "sources_measured": round((measured / n if n else 0.0) * 0.30, 4),
        "corroboration": round(corr * 0.20, 4),
        "history": round(min(1.0, hist / 8.0) * 0.15, 4),
        "resolution": round(res * 0.10, 4),
    }
    score = round(sum(parts.values()), 4)
    band = next((b for cut, b in CONFIDENCE_BANDS if score >= cut), "very_low")
    return {
        "band": band, "components": parts, "score_0_1": score,
        "measured_sources": measured, "total_sources": n,
        "not_a_probability_en": (
            "This is a weighted band, not a calibrated probability. No "
            "outcome data has been fed back into the platform yet, so a "
            "figure like '94%' would be false precision about something "
            "that sounds like a chance of being right. The components are "
            "shown so the band can be argued with."),
    }


def report(kind: str, *, title: str, summary_en: str, areas: list[str],
           sectors: list[str] | None = None, evidence: list[dict],
           confidence_inputs: dict, snapshot: dict,
           discrepancy_en: str = "", options: list[str] | None = None,
           observed_at: str = "") -> dict:
    """Bygg en rapport. Höjer på okänd detektionstyp – en rapport utan
    deklarerad observationsform får inte finnas."""
    spec = DETECTION_KINDS.get(kind)
    if spec is None:
        raise ValueError(f"unknown detection kind: {kind}. "
                         f"Choose {', '.join(DETECTION_KINDS)}")
    if not evidence:
        raise ValueError("a report needs its evidence listed")
    bad = [o for o in (options or []) if o not in ACTION_OPTIONS]
    if bad:
        raise ValueError(f"unknown option(s): {bad}")

    conf = confidence(confidence_inputs)
    w = worthiness(snapshot)
    rec = {
        "kind": kind, "kind_label_en": spec["label_en"],
        "title": title, "summary_en": summary_en,
        # Vad som setts, och vad det inte visar. Alltid båda.
        "observation_en": spec["observation_en"],
        "discrepancy_en": discrepancy_en,
        "does_not_establish_en": spec["never_en"],
        "evidence": [dict(e) for e in evidence],
        "confidence": conf,
        "areas": list(areas), "sectors": list(sectors or spec["sectors"]),
        "priority": {"score": w["total"], "band": w["priority"],
                     "factors": w["factors"], "reason": w["reason"]},
        "worthy": w["worthy"],
        # Alternativ med vad de avgör – aldrig en uppmaning.
        "options": [{"option": o, "resolves_en": ACTION_OPTIONS[o]}
                    for o in (options or ["watch", "verify_desk", "none"])],
        "no_recommendation_en": (
            "The platform does not tell you what to do. Each option states "
            "what it would resolve; the choice, and the outcome, are yours."),
        "observed_at": observed_at,
        "framing": framing_disclosure({
            "detection": kind, "confidence": conf["band"],
            "not_causal": True, "not_a_legal_finding": True}),
    }
    rec["id"] = canonical_hash({"kind": kind, "title": title,
                                "areas": sorted(areas),
                                "observed_at": observed_at})
    return rec


def _matches(rec: dict, areas: list[str], sectors: list[str]) -> bool:
    if areas:
        ra = [a.lower() for a in rec["areas"]]
        if not any(a.lower() in ra or any(x.startswith(a.lower() + "-")
                                          for x in ra) for a in areas):
            return False
    if sectors:
        rs = [s.lower() for s in rec["sectors"]]
        if not any(s.lower() in rs for s in sectors):
            return False
    return True


def _apply_plan_scope(plan: str, areas: list[str], sectors: list[str],
                      own_assets: bool) -> tuple[list[str], list[str], bool, dict]:
    """Vad abonnemanget tillåter briefen att avgränsas på.

    Att tyst ignorera en avgränsning kunden bad om är samma fel som att tyst
    degradera en källa: svaret blir ett annat än det beställda, och ingen får
    veta det. Därför tas avgränsningen bort OCH redovisas, med vilken nivå som
    bär den.
    """
    if not plan:
        return areas, sectors, own_assets, {}
    scope = offering_brief_scope(plan)
    dropped = []
    if areas and not scope["may_scope_by_area"]:
        dropped.append({"asked_for": "areas", "values": list(areas)})
        areas = []
    if sectors and not scope["may_scope_by_sector"]:
        dropped.append({"asked_for": "sectors", "values": list(sectors)})
        sectors = []
    if own_assets and not scope["may_use_own_assets"]:
        dropped.append({"asked_for": "own_assets", "values": []})
        own_assets = False
    note = {"plan": scope["plan"], "scope": scope["scope"],
            "label_en": scope["label_en"], "why_en": scope["why_en"]}
    if dropped:
        note["not_applied"] = dropped
        note["not_applied_en"] = (
            f"This brief is scoped as '{scope['label_en']}' on the "
            f"{scope['plan']} plan, so "
            + ", ".join(d["asked_for"] for d in dropped)
            + " was not applied. The result below is the wider brief, not "
              "the narrower one that was asked for — see /v1/offering.")
    return areas, sectors, own_assets, note


def daily_brief(reports: list[dict], *, areas: list[str] | None = None,
                sectors: list[str] | None = None, limit: int = 20,
                date: str = "", plan: str = "",
                own_assets: bool = False) -> dict:
    """Dagens brief: filtrerad på område/bransch, sorterad på beslutsvärde.

    Sorteras ALDRIG på tidpunkt. Det som mest sannolikt kräver uppmärksamhet
    ligger överst, oavsett när det upptäcktes.

    `plan` avgör hur fint briefen får avgränsas (Explorer publikt, Professional
    region+bransch, Enterprise även egna tillgångar). Utan `plan` gäller ingen
    begränsning – motorn är inte affärslogikens ägare, API-lagret är.
    """
    areas = areas or []
    sectors = sectors or []
    areas, sectors, own_assets, plan_note = _apply_plan_scope(
        plan, areas, sectors, own_assets)
    scoped = [r for r in reports if _matches(r, areas, sectors)]
    worthy = [r for r in scoped if r.get("worthy")]
    worthy.sort(key=lambda r: -r["priority"]["score"])
    kept = worthy[:limit]

    scope_en = (", ".join(areas) if areas else "everywhere covered")
    if sectors:
        scope_en += " · " + ", ".join(sectors)

    if not kept:
        # En tyst dag ÄR ett svar. Att fylla briefen med brus för att den
        # ska se värdefull ut är precis hur den slutar vara det.
        return {
            "date": date, "scope_en": scope_en,
            "reports": [], "count": 0,
            "considered": len(scoped), "below_threshold": len(scoped),
            "headline_en": (
                f"Nothing crossed the threshold for {scope_en} today."
                + (f" {len(scoped)} change(s) were examined and none reached "
                   f"the significance floor." if scoped else
                   " No changes were examined for this scope.")),
            "quiet_day_en": "A quiet brief is a real result. A brief that "
                            "always has something in it will eventually be "
                            "filled with noise to keep it full.",
            "plan_scope": plan_note,
            "framing": framing_disclosure({"scope": scope_en,
                                           "sorted_by": "decision value",
                                           "empty_is_valid": True}),
        }

    by_band: dict[str, int] = {}
    for r in kept:
        by_band[r["priority"]["band"]] = by_band.get(r["priority"]["band"], 0) + 1
    top = kept[0]
    return {
        "date": date, "scope_en": scope_en,
        "reports": kept, "count": len(kept),
        "considered": len(scoped),
        "below_threshold": len(scoped) - len(worthy),
        "by_priority": by_band,
        "headline_en": (f"{len(kept)} report(s) for {scope_en}. Highest "
                        f"decision value: {top['title']}"),
        "sorted_by_en": "Decision value, not recency — what most likely "
                        "needs attention is first, whenever it was found.",
        "suppressed_en": (f"{len(scoped) - len(worthy)} change(s) were "
                          f"examined and held below the significance floor."),
        "plan_scope": plan_note,
        "framing": framing_disclosure({"scope": scope_en,
                                       "sorted_by": "decision value",
                                       "not_causal": True}),
    }


def catalog() -> dict:
    """Vad briefen kan upptäcka, och vad varje form INTE visar."""
    return {
        "detection_kinds": [{"kind": k, **v, "sectors": list(v["sectors"])}
                            for k, v in DETECTION_KINDS.items()],
        "options": [{"option": k, "resolves_en": v}
                    for k, v in ACTION_OPTIONS.items()],
        "confidence_inputs": list(CONFIDENCE_INPUTS),
        "priority_bands": [b for _, b in PRIORITY],
        "note_en": "Every detection kind declares what it observes and what "
                   "that observation does not establish. The platform "
                   "reports a discrepancy against a register; it never "
                   "reports a legal finding.",
    }
