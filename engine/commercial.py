"""Hur kunden betalar — fem sätt, för att kunder är olika, inte för att
vi inte bestämt oss.

Bakgrunden: koden sa "ingen månadsavgift, provision per levererad lead"
medan landvex.com sa "enterprise-prissättning, tre månaders pilot följt
av årlig prenumeration". Det såg ut som två affärsmodeller publicerade
samtidigt — alltså en motsägelse. Det var det inte. Det var två av flera
paketeringar, var och en riktig för sin kund, beskrivna på var sitt
ställe som om den var den enda.

En franchisekedja köper LEADS: de vet vad ett öppnat läge är värt och
vill betala per stycke. En kommun kan inte köpa leads — de har en
budgetcykel, en upphandling och ett planeringsår, och de köper en PILOT
som blir en prenumeration. Ett försäkringsbolag köper varken; de köper en
FÖRMÅGA som står och går över hela beståndet. Att tvinga in alla tre i en
prislista gör att två av dem inte kan köpa alls.

Varje paketering här bär:

    buys_en       vad kunden faktiskt får för pengarna
    pays_when_en  när betalningen utlöses — den rad som avgör om en
                  inköpsavdelning kan hantera den
    fits_en       vilken sorts kund den passar, och varför
    unit_en       vad som räknas: en lead, en månad, ett uppdrag
    built         om paketeringen går att LEVERERA idag

`built` är den viktigaste. Att sälja en paketering vars leveranskedja
inte är sluten är inte optimism, det är en skuld som förfaller vid första
fakturan. Ett test kräver att varje paketering som är märkt levererbar
kan peka ut vad i koden som levererar den.

Rent stdlib. Registret är DATA: en ny paketering är en rad, inte en gren.
"""
from __future__ import annotations


def _p(id_: str, name_en: str, buys_en: str, pays_when_en: str,
       fits_en: str, unit_en: str, built: bool, depends_on_en: str = "",
       plans: tuple[str, ...] = ()) -> dict:
    return {"id": id_, "name_en": name_en, "buys_en": buys_en,
            "pays_when_en": pays_when_en, "fits_en": fits_en,
            "unit_en": unit_en, "built": built,
            "depends_on_en": depends_on_en, "plans": plans}


PACKAGINGS: tuple[dict, ...] = (
    _p("open", "Open",
       "Public findings, and enough of the platform to judge whether it "
       "is worth anything to you.",
       "Never. There is no invoice and no card on file.",
       "A resident checking a claim about their own street, a student, a "
       "journalist on a deadline. Also every buyer's first hour.",
       "nothing", True,
       plans=("free",)),

    _p("per_lead", "Commission per lead",
       "A delivered opportunity — an identified location with the "
       "decision card behind it. You pay for the ones you receive.",
       "On delivery of each lead, graded by opportunity score.",
       "Retail chains, franchises and operators who already know what an "
       "opened location is worth. No budget approval needed to start, "
       "which is why it is the lowest-friction way in.",
       "one delivered lead", True,
       depends_on_en="engine/commission.py grades the score; the decision "
                     "card is /v1/report",
       plans=("pro",)),

    _p("per_mission", "Per mission",
       "One question answered from the field: observations collected at "
       "exactly the locations the decision depends on, delivered within "
       "24–72 hours of the mission starting.",
       "Per mission, before dispatch.",
       "Anyone with one decision and a deadline — a site visit they "
       "cannot make, a claim they need settled this week. The natural "
       "first purchase after the open tier.",
       "one mission", False,
       depends_on_en="NOT DELIVERABLE YET: mission dispatch, media capture "
                     "with preserved sensor metadata and the Vision step "
                     "that reads it are not built. Selling it today "
                     "promises a chain that is not closed.",
       plans=("pro",)),

    _p("pilot_then_subscription", "Pilot, then annual subscription",
       "Three months proving it on your own area or portfolio, then a "
       "standing intelligence subscription for the year.",
       "Pilot fee up front, subscription annually thereafter.",
       "Municipalities, regions and authorities. They cannot buy leads — "
       "they have a budget cycle, a procurement process and a planning "
       "year, and a pilot is the shape that fits all three.",
       "three months, then a year", True,
       depends_on_en="the engines behind it are built; the pilot is a "
                     "commercial wrapper, not a feature",
       plans=("pro", "enterprise")),

    _p("capability_agreement", "Capability agreement",
       "A standing capability: your own detection rules, your own assets "
       "watched continuously, decisions bound to named owners and "
       "resolved against what actually happened.",
       "By agreement. No list price is published, and none is invented "
       "here.",
       "Insurers, banks, utilities, grid and infrastructure owners — "
       "thousands of objects, none of which anyone can watch by hand. "
       "They are not buying answers, they are buying that the watching "
       "never stops.",
       "an agreement", True,
       depends_on_en="/v1/monitors for own rules, /v1/decisions/commit for "
                     "ownership, /v1/brief for the standing brief",
       plans=("enterprise",)),
)

PRINCIPLE_EN = (
    "Five ways to buy, because customers are different — not because the "
    "pricing is undecided. A franchise knows what an opened location is "
    "worth and wants to pay per one; a municipality has a budget cycle "
    "and can only buy a pilot; an insurer is buying that the watching "
    "never stops. Forcing all three into one price list means two of "
    "them cannot buy at all."
)

HONESTY_EN = (
    "One packaging is marked as not deliverable. Per-mission delivery "
    "depends on a chain — dispatch, capture with preserved sensor "
    "metadata, and the step that reads the media — that is not closed "
    "yet. It is listed so nobody sells it by accident, and so the work "
    "it needs is visible next to the revenue it would carry."
)


def for_plan(plan_id: str) -> list[dict]:
    return [p for p in PACKAGINGS if plan_id in p["plans"]]


def deliverable() -> list[dict]:
    return [p for p in PACKAGINGS if p["built"]]


def catalog() -> dict:
    return {
        "packagings": list(PACKAGINGS),
        "count": len(PACKAGINGS),
        "deliverable_count": len(deliverable()),
        "principle_en": PRINCIPLE_EN,
        "honesty_en": HONESTY_EN,
    }
