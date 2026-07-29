"""Sponsrade uppdrag — varumärken finansierar, zoomers utför, aggregat
levereras. Och gränsen mot personen är byggd, inte lovad.

Två uppdragsklasser, samma motor:

  verification   fota gatan, verifiera skylten, dokumentera övergångs-
                 stället — sponsorn köper LÄGESBILD
  content        Garmin-klockan på löprundan, McFlurryn utomhus,
                 IKEA-produkten i hemmet — sponsorn köper AUTENTISKT
                 MATERIAL, och då krävs en avtalsreferens för
                 rättigheterna INNAN ett enda uppdrag genereras

Snittet mot quiXzoom (beslutat i docs/sponsored-rewards-design.md):

  * Landvex bär kampanjen, budgeten, belönings-UTBUDET, domarna
    (Vision-ledets verdikt som data) och k-golvade aggregat.
  * quiXzoom bär människan: plånboken, utbetalningen, bilden,
    rättighetskedjan och all individprofilering (med samtycke, där).
    Landvex lagrar kontoreferenser och avräkningsreferenser — aldrig
    saldon, aldrig media, aldrig beteendemönster per person.

Spärrarna som är lag här:

  * **Sponsorn är synlig för zoomern.** `sponsor_visible_en` är ett
    obligatoriskt fält i uppdragskroppen — "det framgår vilken sponsor
    som finansierar" är ett fältkrav, inte en policytext.
  * **Budget är ett tak.** En kampanj vars budget är förbrukad
    genererar ingenting och säger det. Pacing (max per dygn) kan
    aldrig tyst överskrida taket.
  * **k-golvet (k ≥ 5).** En "aggregerad" cell med fyra personer i är
    individnivå med ett medelvärde på. Celler under golvet undertrycks
    och RÄKNAS — sponsorn ser hur mycket som undertrycktes, aldrig vad.
  * **Co-sponsring är rader** med andelar som summerar till 1,0.
  * **Fullbordan registreras med dom och region — aldrig med person.**
    Avräkningsreferensen pekar in i quiXzoom där zoomern får betalt.

Rent stdlib.
"""
from __future__ import annotations

import time as _time
import uuid

# ── Belöningsformer och uppdragsklasser: tabeller, inte grenar ─────────
REWARD_KINDS: dict[str, dict] = {
    "cash": {"label_en": "Cash payout", "unit": "currency"},
    "gift_card": {"label_en": "Gift card", "unit": "currency"},
    "voucher": {"label_en": "Digital voucher", "unit": "item"},
    "discount_code": {"label_en": "Discount code", "unit": "item"},
    "loyalty_points": {"label_en": "Loyalty points", "unit": "points"},
    "choice": {"label_en": "Zoomer's choice among the offered rewards",
               "unit": "meta"},
}

MISSION_CLASSES: dict[str, dict] = {
    "verification": {
        "label_en": "Verify or document a real-world condition",
        "needs_rights_ref": False,
        "examples_en": ("photograph a street", "verify a sign",
                        "document a pedestrian crossing")},
    "content": {
        "label_en": "Create authentic brand imagery",
        "needs_rights_ref": True,
        "examples_en": ("a Garmin watch on a trail run",
                        "a McFlurry outdoors in daylight",
                        "an IKEA product in a real home")},
}

# Under så här många fullbordanden i en cell visas ingen cell alls.
K_MIN = 5


class SponsorshipRefused(ValueError):
    """Kampanjen eller uppdraget gick inte att skapa, och varför."""


# ── Kampanjen ──────────────────────────────────────────────────────────
def campaign(id: str, sponsor_visible_en: str, mission_class: str,
             brief_en: str, *, budget: float, currency: str = "SEK",
             rewards: tuple[dict, ...] = (), market: str = "se",
             region_codes: tuple[str, ...] = (),
             max_per_day: int = 0,
             rights_agreement_ref: str = "",
             co_sponsors: tuple[dict, ...] = (),
             tenant: str = "") -> dict:
    """Skapa en kampanj — eller vägra med ett skäl som går att åtgärda."""
    if not id:
        raise SponsorshipRefused("a campaign needs an id")
    if not tenant:
        raise SponsorshipRefused(
            "a campaign needs a tenant: budgets and statistics are one "
            "customer's own, and without a tenant they would be "
            "everyone's")
    if not sponsor_visible_en.strip():
        raise SponsorshipRefused(
            "sponsor_visible_en is what the ZOOMER sees before "
            "accepting. A mission whose funder is hidden is exactly the "
            "arrangement this engine refuses to create.")
    if mission_class not in MISSION_CLASSES:
        raise SponsorshipRefused(
            f"unknown mission class {mission_class!r}; choose "
            f"{', '.join(sorted(MISSION_CLASSES))}")
    if MISSION_CLASSES[mission_class]["needs_rights_ref"] \
            and not rights_agreement_ref.strip():
        raise SponsorshipRefused(
            "content missions transfer usage rights to the sponsor — "
            "without a rights_agreement_ref the material could not "
            "lawfully be used, and a mission whose result nobody may "
            "use is a promise that cannot be kept. The agreement "
            "itself lives with quiXzoom; this is its reference.")
    if not brief_en.strip():
        raise SponsorshipRefused(
            "brief_en is what the zoomer is asked to DO. Empty brief, "
            "no mission.")
    if budget <= 0:
        raise SponsorshipRefused("budget must be positive — it is the "
                                 "cap every order is counted against")
    if not rewards:
        raise SponsorshipRefused(
            "a sponsored mission without a reward offer is unpaid work "
            "dressed as a campaign")
    for r in rewards:
        if r.get("kind") not in REWARD_KINDS:
            raise SponsorshipRefused(
                f"unknown reward kind {r.get('kind')!r}; choose "
                f"{', '.join(sorted(REWARD_KINDS))}")
        if REWARD_KINDS[r["kind"]]["unit"] == "currency" \
                and not r.get("amount"):
            raise SponsorshipRefused(
                f"reward {r['kind']!r} needs an amount")
    if co_sponsors:
        total = sum(float(c.get("share", 0)) for c in co_sponsors)
        if abs(total - 1.0) > 1e-9:
            raise SponsorshipRefused(
                f"co-sponsor shares sum to {total}, not 1.0 — an "
                f"unallocated share is a bill nobody agreed to pay")
        for c in co_sponsors:
            if not c.get("name_en"):
                raise SponsorshipRefused("every co-sponsor is named")
    return {
        "id": id, "tenant": tenant,
        "sponsor_visible_en": sponsor_visible_en.strip(),
        "mission_class": mission_class, "brief_en": brief_en.strip(),
        "budget": float(budget), "currency": currency,
        "spent": 0.0, "ordered": 0,
        "rewards": tuple(dict(r) for r in rewards),
        "market": market, "region_codes": tuple(region_codes),
        "max_per_day": int(max_per_day),
        "rights_agreement_ref": rights_agreement_ref.strip(),
        "co_sponsors": tuple(dict(c) for c in co_sponsors),
        "created_at": _time.time(), "status": "active",
    }


def _mission_cost(kamp: dict) -> float:
    """Kampanjens kostnad per uppdrag = största kontantbelöningen i
    utbudet (zoomern kan välja den). Poäng/kuponger utan belopp
    kostar 0 här — deras kostnad bor i sponsorns egna system."""
    return max((float(r.get("amount", 0)) for r in kamp["rewards"]),
               default=0.0)


def can_order(kamp: dict, *, today_count: int = 0) -> dict:
    """Får ETT uppdrag till genereras? Svaret bär alltid skälet."""
    if kamp.get("status") != "active":
        return {"allowed": False,
                "why_en": f"campaign is {kamp.get('status')!r}"}
    kostnad = _mission_cost(kamp)
    if kamp["spent"] + kostnad > kamp["budget"]:
        return {"allowed": False, "why_en": (
            f"budget cap: {kamp['spent']:.2f} of {kamp['budget']:.2f} "
            f"{kamp['currency']} committed, next mission costs "
            f"{kostnad:.2f}. The cap is a cap — nothing is ordered "
            f"past it, and this message is the pacing report.")}
    if kamp["max_per_day"] and today_count >= kamp["max_per_day"]:
        return {"allowed": False, "why_en": (
            f"pacing: {today_count} mission(s) already ordered today, "
            f"max_per_day is {kamp['max_per_day']}. Tomorrow counts "
            f"from zero.")}
    return {"allowed": True, "why_en": "", "cost": kostnad}


def mission_body(kamp: dict, *, region_code: str = "",
                 lat: float | None = None,
                 lon: float | None = None) -> dict:
    """Uppdragskroppen som går till quiXzoom — transparensen är fält.

    Ingen person förekommer: quiXzoom väljer/riktar utförare enligt
    sina egna samtycken. Landvex säger VAD, VAR, VEM SOM BETALAR och
    VAD SOM ERBJUDS.
    """
    klass = MISSION_CLASSES[kamp["mission_class"]]
    return {
        "campaign_ref": kamp["id"],
        "mission_class": kamp["mission_class"],
        "title": f"Sponsored: {kamp['brief_en'][:60]}",
        "brief_en": kamp["brief_en"],
        # Zoomern ska veta vad hen deltar i INNAN accept — fälten är
        # obligatoriska, inte en policy någon annanstans.
        "sponsor_visible_en": kamp["sponsor_visible_en"],
        "what_this_means_en": (
            f"This mission is funded by {kamp['sponsor_visible_en']}. "
            + ("The material you create is licensed to the sponsor "
               "under the agreement referenced below. "
               if klass["needs_rights_ref"] else
               "The observation you record informs the sponsor's "
               "aggregated statistics — never your identity. ")
            + "Your payout, your data and your consent live with "
              "quiXzoom, not with the sponsor."),
        "rewards_offered": [dict(r) for r in kamp["rewards"]],
        "rights_agreement_ref": kamp["rights_agreement_ref"],
        "location": {"region_code": region_code, "lat": lat, "lon": lon},
        "required_media": ["photo"],
    }


# ── Fullbordanden: dom och region — aldrig person ──────────────────────
_FORBIDDEN_COMPLETION_FIELDS = ("zoomer_id", "zoomer", "user_id", "name",
                                "email", "phone", "device_id", "account")


def completion(campaign_id: str, mission_id: str, *,
               region_code: str = "", quality_band: str = "",
               verdicts: dict | None = None,
               settlement_ref: str = "", tenant: str = "",
               completed_at: float = 0.0) -> dict:
    """Registrera EN fullbordan. Persondata vägras vid dörren."""
    if not campaign_id or not mission_id:
        raise SponsorshipRefused(
            "a completion needs campaign_id and mission_id — without "
            "the mission reference it cannot be tied to its evidence")
    for f in _FORBIDDEN_COMPLETION_FIELDS:
        if f in (verdicts or {}):
            raise SponsorshipRefused(
                f"verdicts carry {f!r}: completions record WHAT was "
                f"verified and WHERE — never WHO. The person lives "
                f"with quiXzoom.")
    return {
        "id": uuid.uuid4().hex[:12], "tenant": tenant,
        "campaign_id": campaign_id, "mission_id": mission_id,
        "region_code": region_code, "quality_band": quality_band,
        # Vision-ledets domar som data: produkt_i_bild, utomhus,
        # färskhet … nycklar bestäms av verifieringskraven, inte här.
        "verdicts": dict(verdicts or {}),
        "settlement_ref": settlement_ref,
        "completed_at": float(completed_at) or _time.time(),
    }


# ── Lagret (samma mönster som inspections) ─────────────────────────────
_STORE = None
_KAMPANJER: dict[str, dict] = {}
_FULLBORDANDEN: list[dict] = []


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def save_campaign(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_campaign", None):
        return _STORE.save_campaign(rec)
    _KAMPANJER[rec["id"]] = dict(rec)
    return rec["id"]


def all_campaigns(tenant: str | None = None) -> list[dict]:
    rader = (_STORE.all_campaigns() if _STORE is not None
             and getattr(_STORE, "all_campaigns", None)
             else list(_KAMPANJER.values()))
    return [r for r in rader if tenant is None or r["tenant"] == tenant]


def save_completion(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_completion", None):
        return _STORE.save_completion(rec)
    _FULLBORDANDEN.append(dict(rec))
    return rec["id"]


def all_completions(tenant: str | None = None,
                    campaign_id: str = "") -> list[dict]:
    rader = (_STORE.all_completions() if _STORE is not None
             and getattr(_STORE, "all_completions", None)
             else list(_FULLBORDANDEN))
    return [r for r in rader
            if (tenant is None or r["tenant"] == tenant)
            and (not campaign_id or r["campaign_id"] == campaign_id)]


def reset() -> None:
    """Endast för tester."""
    _KAMPANJER.clear()
    _FULLBORDANDEN.clear()


# ── Sponsorstatistiken: aggregat med k-golv ────────────────────────────
def stats(campaign_id: str, *, tenant: str) -> dict:
    """Vad sponsorn får se. Celler under k-golvet undertrycks och
    RÄKNAS — hur mycket som undertrycktes är synligt, aldrig vad."""
    kamp = next((k for k in all_campaigns(tenant)
                 if k["id"] == campaign_id), None)
    if kamp is None:
        raise SponsorshipRefused(f"unknown campaign {campaign_id!r} "
                                 f"for this tenant")
    rader = all_completions(tenant, campaign_id)
    per_region: dict[str, int] = {}
    per_vecka: dict[str, int] = {}
    band: dict[str, int] = {}
    for r in rader:
        per_region[r["region_code"] or "unknown"] = \
            per_region.get(r["region_code"] or "unknown", 0) + 1
        vecka = _time.strftime("%G-W%V", _time.gmtime(r["completed_at"]))
        per_vecka[vecka] = per_vecka.get(vecka, 0) + 1
        if r["quality_band"]:
            band[r["quality_band"]] = band.get(r["quality_band"], 0) + 1
    synliga = {k: v for k, v in per_region.items() if v >= K_MIN}
    dolda = len(per_region) - len(synliga)
    return {
        "campaign_id": campaign_id,
        "sponsor_visible_en": kamp["sponsor_visible_en"],
        "completed": len(rader), "ordered": kamp["ordered"],
        "completion_rate": (round(len(rader) / kamp["ordered"], 3)
                            if kamp["ordered"] else None),
        "budget": {"cap": kamp["budget"], "committed": kamp["spent"],
                   "currency": kamp["currency"]},
        "regions": synliga,
        "regions_suppressed": dolda,
        "suppressed_note_en": (
            f"{dolda} region cell(s) held fewer than {K_MIN} "
            f"completions and are not shown: an aggregate over four "
            f"people is an individual with an average on it."),
        "weeks": dict(sorted(per_vecka.items())),
        "quality_bands": band,
        "roi_basis_en": (
            "ROI here is committed budget against completed missions — "
            "it assumes every completion is equally valuable to the "
            "sponsor, which is the sponsor's judgement to refine, not "
            "ours to hide."),
        "cannot_en": (
            "No individual appears in any cell, and no consent to the "
            "contrary is handled here: per-person data, where it "
            "lawfully exists at all, lives with quiXzoom under its own "
            "consent. This surface cannot say WHO — only what, where "
            "(k-floored) and when."),
    }


def catalog() -> dict:
    return {
        "what_en": ("Sponsored missions: brands fund verification or "
                    "authentic-content missions; zoomers choose among "
                    "offered rewards; sponsors see k-floored aggregates. "
                    "The wallet, the payout, the media and every "
                    "per-person record live with quiXzoom."),
        "mission_classes": {k: {kk: vv for kk, vv in v.items()}
                            for k, v in MISSION_CLASSES.items()},
        "reward_kinds": REWARD_KINDS,
        "k_floor": K_MIN,
        "transparency_en": ("The funding sponsor is a required, "
                            "zoomer-visible field on every mission — "
                            "a mission whose funder is hidden is "
                            "refused at creation."),
        "cannot_en": ("This engine cannot pay anyone and cannot see "
                      "anyone: it counts missions and money, and the "
                      "settlement reference points into quiXzoom where "
                      "the person, the consent and the payout live."),
    }
