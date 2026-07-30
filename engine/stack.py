"""Tre lager, tre bolag, tre saker att köpa — och vad det översta tillför.

Den fråga varje storkund ställer, förr eller senare: *vi kan ju koppla
quiXzoom och AAMOS via API själva — varför behöver vi Landvex?*

Det är en rimlig fråga och den förtjänar ett svar som inte är
marknadsföring. Svaret finns i vad varje lager faktiskt levererar:

    quiXzoom   RÅ BILDDATA. Beställs i serier eller styckvis, med GPS,
               IMU, kompass och tidsstämpel bevarade per bildruta.
               Kunden får pixlar med proveniens.

    AAMOS      MODELLERNA. Läser bilderna och detekterar — manipulation
               på en betalautomat, en infrastrukturrisk. Kunden får
               detektioner.

    Landvex    BESLUTSSTÖDET. Väger detektionerna mot andra sensorer och
               mot trovärdig statistik, avgör vad som är RELEVANT för
               just det beslut kunden ska fatta, och levererar det
               färdigpaketerat.

En kund SKA kunna koppla de två understa själv — den vägen är öppen med
flit, och för ett internt system som redan vet vad det letar efter är
den ofta rätt. Det Landvex tillför är inte åtkomst utan **omdöme**: vad
som är värt att titta på, hur säkert det är, vad det INTE avgör, vem som
bär beslutet, och om förra beslutet höll.

Ingen kommer att sitta och titta på bilderna. Det är hela poängen med
det översta lagret: kunden vill ha slutsatsen, inte materialet.

`self_serve_gap_en` är den ärliga raden — vad en kund som byggt ihop de
två understa själv fortfarande saknar. Den ska läsas som en lista över
arbete, inte som ett hot.

Rent stdlib. Registret är DATA.
"""
from __future__ import annotations


LAYERS: tuple[dict, ...] = (
    {"id": "capture", "order": 1, "company": "quiXzoom",
     "sells_en": "Raw image data, ordered in series or one at a time.",
     "delivers_en": "Frames with provenance: GPS, IMU, compass and "
                    "timestamp preserved per frame, collected by verified "
                    "contributors at the locations you name.",
     "buys_it_en": "Anyone who needs eyes somewhere they are not — "
                   "including customers who never touch the other two "
                   "layers.",
     "you_still_do_en": "Everything after the pixels: deciding what to "
                        "look for, looking, and deciding what it means.",
     "in_this_repo": "engine/datasources/quixzoom_direct.py · "
                     "/api/quixzoom/missions"},

    {"id": "perception", "order": 2, "company": "AAMOS",
     "sells_en": "The models that read the imagery.",
     "delivers_en": "Detections — tampering on a payment terminal, an "
                    "infrastructure risk — and the contradiction signals "
                    "behind them.",
     "buys_it_en": "Teams with their own internal systems, who wire "
                   "quiXzoom and AAMOS together by API and route the "
                   "detections into what they already run. That path is "
                   "open on purpose.",
     "you_still_do_en": "Weigh a detection against everything else that "
                        "is true about the place, decide whether it "
                        "matters for the decision at hand, and carry the "
                        "consequence.",
     "in_this_repo": "integrations/aamos.py · /api/aamos/apollo/"
                     "contradictions"},

    {"id": "decision", "order": 3, "company": "Landvex",
     "sells_en": "The finished decision support.",
     "delivers_en": "Detections fused with other sensor streams and with "
                    "credible statistics, filtered to what is relevant "
                    "for the decision you actually have to make, with the "
                    "basis, the uncertainty band, what it does not "
                    "settle, and who carries the outcome.",
     "buys_it_en": "Large customers, authorities and enterprises who want "
                   "the conclusion, not the material — and who have to "
                   "defend the decision afterwards.",
     "you_still_do_en": "Decide. The platform never recommends; it hands "
                        "over the basis and names the owner.",
     "in_this_repo": "the rest of engine/"},
)

# Vad en kund som kopplat ihop de två understa själv fortfarande saknar.
# Skrivet som arbete, inte som argument: varje rad är något de får bygga.
SELF_SERVE_GAP: tuple[dict, ...] = (
    {"missing_en": "Everything that is true about the place besides the "
                   "image",
     "why_en": "A detection is one observation. Whether it matters depends "
               "on traffic, weather, permits, the business register, the "
               "energy grid and the statistics for that region — dozens of "
               "streams that have to be fetched, normalised and kept "
               "honest when they fail.",
     "here_en": "engine/datasources/ · /v1/sources"},
    {"missing_en": "A reason to believe it",
     "why_en": "One network cannot corroborate itself. Independence, "
               "modality and agreement decide how much a second source "
               "actually adds — and two sources that disagree are a "
               "weaker basis than one, not a stronger one.",
     "here_en": "/v1/corroboration"},
    {"missing_en": "Relevance, so nobody reads a thousand detections",
     "why_en": "Nobody will sit and go through the material by hand. "
               "Something has to rank what is worth surfacing for THIS "
               "decision and drop the rest without hiding that it did.",
     "here_en": "/v1/worthiness · /v1/feeds"},
    {"missing_en": "A refusal when the basis is thin",
     "why_en": "An internal pipeline will happily produce a number from "
               "nothing. Saying 'no count available and none invented' is "
               "a design decision somebody has to make, and then defend "
               "every time it is inconvenient.",
     "here_en": "/v1/saturation"},
    {"missing_en": "Accountability that survives the meeting",
     "why_en": "A decision bound to three named owners with a measurable "
               "expected outcome, resolvable later against what actually "
               "happened.",
     "here_en": "/v1/decisions/commit"},
    {"missing_en": "Evidence that the model is any good",
     "why_en": "Calibration against real outcomes over time. It cannot be "
               "bought or shortcut; it takes calendar time for everyone, "
               "including us.",
     "here_en": "/v1/outcomes/calibration"},
)

PRINCIPLE_EN = (
    "Three layers, three companies, three things to buy. quiXzoom sells "
    "the pixels, AAMOS sells the models that read them, Landvex sells the "
    "decision. Wiring the bottom two together yourself is a supported "
    "path, not a workaround — what the top layer adds is judgement: what "
    "is worth looking at, how sure it is, what it does not settle, and "
    "who carries the outcome."
)

NOBODY_WILL_LOOK_EN = (
    "Nobody is going to sit and review the imagery by hand. That is the "
    "entire reason the top layer exists: the customer wants the "
    "conclusion, not the material — and wants to be able to defend it "
    "afterwards."
)


def layer(id_: str) -> dict | None:
    return next((x for x in LAYERS if x["id"] == id_), None)


def catalog() -> dict:
    return {
        "layers": list(LAYERS),
        "self_serve_gap": list(SELF_SERVE_GAP),
        "principle_en": PRINCIPLE_EN,
        "nobody_will_look_en": NOBODY_WILL_LOOK_EN,
    }
