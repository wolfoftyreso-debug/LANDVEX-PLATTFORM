"""Infrastrukturövervakning — en observation åldras, och det syns.

Crowdsourcade observationer av den fysiska miljön: cykelparkeringar,
bilparkeringar, hållplatser, lekplatser, återvinningsstationer, hamnar,
badplatser, pendelparkeringar, cykelpumpar, offentliga toaletter.

**Den kommersiellt avgörande skillnaden är inte vad vi mäter — det är
att en kund vet vilken datakvalitet hen köper.** Därför är hela modulen
byggd kring EN egenskap som saknas i vanliga observationsdatabaser:

    VOLATILITET. Hur länge ett observerat värde fortfarande är ett
    besked om NU.

"Fjorton lediga platser" är sant i tio minuter. "Cykelstället är
skadat" är sant i veckor. Att servera båda som "aktuell status" är
samma fel som att servera gårdagens väder som prognos — och det är ett
fel som kostar pengar hos en parkeringsoperatör som dirigerar bilar.

Fyra spärrar, alla lag i koden:

  * **En färskvara som gått ut serveras ALDRIG som aktuell.** Den
    serveras som historik med sin ålder, och statusfältet säger
    `stale`. Ingen kund kan av misstag läsa den som nuläge.
  * **Ingenting uppskattas.** Ingen interpolation, ingen modell som
    fyller i mellan observationer. Frågar någon "hur många platser är
    lediga nu" och senaste verifieringen är sex timmar gammal är svaret
    observationen MED sin ålder och en vägran att kalla den aktuell —
    aldrig ett skattat tal. Ett skattat tal ser ut precis som ett mätt.
  * **Tillförlitlighet är ett BAND, aldrig en poäng.** Specen bad om en
    "Confidence Score"; kodbasens korroboreringsdoktrin förbjuder
    procentsatser, eftersom ett tal som "84 %" bjuder in till att
    multipliceras vidare i kalkyler det inte bär. Samma band som resten
    av plattformen: strong / moderate / weak / none.
  * **SLA räknas ur historiken, aldrig ur avtalet.** En utlovad
    kontrollfrekvens som inte hållits ska synas som ett brott, inte
    som en siffra i ett säljblad.

Rent stdlib.
"""
from __future__ import annotations

import time as _time
import uuid

from .corroboration import assess as corroborate

# ── Observationstyper: värdet, enheten och HUR SNABBT det åldras ───────
# `fresh_minutes`  — så länge värdet är ett besked om NU.
# `stale_minutes`  — bortom detta är det historik, inte status.
# Mellan dem: `ageing` — användbart med sin ålder utskriven, aldrig som
# ett påstående om nuläget.
OBS_KINDS: dict[str, dict] = {
    "count": {"label_en": "Counted quantity", "unit": "items"},
    "ratio": {"label_en": "Share of capacity", "unit": "0–1"},
    "works": {"label_en": "Working / not working", "unit": "bool"},
    "condition": {"label_en": "Condition band", "unit": "band"},
}

CONDITION_BANDS = ("good", "acceptable", "poor", "unusable")


def _o(id: str, label_en: str, kind: str, fresh_minutes: float,
       stale_minutes: float, cannot_en: str, *,
       weather_sensitive: bool = False) -> dict:
    """`weather_sensitive`: regn eller snöfall OGILTIGFÖRKLARAR fältet
    genom händelsen, inte genom klockan — en färsk snöavläsning från i
    morse är värdelös efter ett skyfall, hur ung den än är."""
    return {"id": id, "label_en": label_en, "kind": kind,
            "fresh_minutes": fresh_minutes,
            "stale_minutes": stale_minutes, "cannot_en": cannot_en,
            "weather_sensitive": weather_sensitive}


# Beläggning åldras på minuter. Skador åldras på veckor. Skillnaden är
# hela produkten.
_FLYKTIG = 20.0        # beläggning, lediga platser
_DAGSFARSK = 720.0     # renhållning, hinder, snö
_TROG = 20160.0        # skador, funktion, skyltning (14 dygn)

OBJECT_TYPES: dict[str, dict] = {
    "bike_parking": {
        "label_en": "Bicycle parking",
        "observations": (
            _o("free_spaces", "Free spaces", "count", _FLYKTIG, 120.0,
               "A count is the moment it was counted. Bicycle parking "
               "turns over in minutes; nothing here predicts the next "
               "hour."),
            _o("occupancy", "Occupancy", "ratio", _FLYKTIG, 120.0,
               "Occupancy is observed, not sensed: a rack half hidden "
               "by a van counts as observed capacity, not as full."),
            _o("misparked", "Misparked bicycles", "count", _DAGSFARSK,
               2880.0,
               "Misparked is a judgement made on site by one person "
               "against the operator's own rule — not a legal finding."),
            _o("rack_damage", "Damaged racks", "condition", _TROG,
               43200.0,
               "Visible damage only. A rack that is loose in the ground "
               "looks intact in a photograph."),
            _o("ev_charging_works", "E-bike charging works", "works",
               _TROG, 43200.0,
               "Observed at the socket, not measured through it: a "
               "charger that indicates ready may still fail under "
               "load."),
            _o("litter", "Litter", "condition", _DAGSFARSK, 2880.0,
               "Litter is a band set by eye, and eyes differ. The band "
               "is comparable over time at the SAME site, less so "
               "between sites.",
               weather_sensitive=True),
        )},
    "car_parking": {
        "label_en": "Car parking",
        "observations": (
            _o("free_spaces", "Free spaces", "count", _FLYKTIG, 90.0,
               "The single most perishable figure in this module. A "
               "count from this morning is not a count for now, and it "
               "is served as history rather than status."),
            _o("occupancy", "Occupancy", "ratio", _FLYKTIG, 90.0,
               "Observed from where the contributor stood. A level "
               "they could not see is not counted as empty."),
            _o("blocked_spaces", "Blocked spaces", "count", _DAGSFARSK,
               2880.0,
               "Blocked is what stood there then — a delivery van "
               "leaves, a snow pile does not."),
            _o("accessible_spaces_free", "Accessible spaces free",
               "count", _FLYKTIG, 90.0,
               "Counting an accessible bay says nothing about whether "
               "the person using it was entitled to."),
            _o("ev_charger_works", "EV chargers working", "works", _TROG,
               43200.0,
               "Observed at the post. Payment, roaming and back-office "
               "failures are invisible from outside."),
            _o("payment_machine_works", "Payment machine working",
               "works", _TROG, 43200.0,
               "A machine that takes cards but not the operator's app "
               "reads as working here."),
            _o("signage_correct", "Signage correct", "condition", _TROG,
               43200.0,
               "Correct against the operator's own rule set as the "
               "contributor understood it — not a legal review."),
            _o("snow_or_obstruction", "Snow or obstruction",
               "condition", _DAGSFARSK, 1440.0,
               "Winter conditions change within hours; a clear reading "
               "from the morning says nothing about the afternoon.",
               weather_sensitive=True),
        )},
    "bus_stop": {
        "label_en": "Bus stop",
        "observations": (
            _o("shelter_condition", "Shelter condition", "condition",
               _TROG, 43200.0,
               "Visible condition from outside only: a cracked pane "
               "shows, a loose fixing does not."),
            _o("timetable_readable", "Timetable readable", "works",
               _TROG, 43200.0,
               "Readable to the contributor who stood there — not an "
               "accessibility assessment."),
            _o("litter", "Litter", "condition", _DAGSFARSK, 2880.0,
               "A band set by eye, and eyes differ — comparable over "
               "time at the same site, less so between sites."),
            _o("snow_or_obstruction", "Snow or obstruction",
               "condition", _DAGSFARSK, 1440.0,
               "Winter conditions change within hours; a clear reading "
               "this morning says nothing about this afternoon.",
               weather_sensitive=True),
        )},
    "playground": {
        "label_en": "Playground",
        "observations": (
            _o("equipment_condition", "Equipment condition", "condition",
               _TROG, 43200.0,
               "This is NOT a safety inspection. Certified playground "
               "inspection is a regulated trade, and a photograph "
               "cannot replace it — a swing whose bearing is worn "
               "looks perfect."),
            _o("litter", "Litter", "condition", _DAGSFARSK, 2880.0,
               "A band set by eye, and eyes differ between "
               "contributors."),
            _o("surface_condition", "Fall surface condition",
               "condition", _TROG, 43200.0,
               "Depth and compaction of a fall surface cannot be seen "
               "from above."),
        )},
    "recycling_station": {
        "label_en": "Recycling station",
        "observations": (
            _o("containers_full", "Containers full", "count", _DAGSFARSK,
               2880.0,
               "Full to the eye at the hatch; a container can be full "
               "at the opening and half empty below."),
            _o("dumping", "Dumping outside containers", "condition",
               _DAGSFARSK, 2880.0,
               "What lay outside at that moment — a pile removed an "
               "hour later still reads as dumping here."),
            _o("litter", "Litter", "condition", _DAGSFARSK, 2880.0,
               "A band set by eye, and eyes differ between "
               "contributors."),
        )},
    "park_and_ride": {
        "label_en": "Park and ride",
        "observations": (
            _o("free_spaces", "Free spaces", "count", _FLYKTIG, 90.0,
               "Perishable within the hour: commuter parking fills on "
               "a schedule this count cannot see."),
            _o("occupancy", "Occupancy", "ratio", _FLYKTIG, 90.0,
               "Observed from where the contributor stood, not sensed "
               "across the whole site."),
            _o("snow_or_obstruction", "Snow or obstruction",
               "condition", _DAGSFARSK, 1440.0,
               "Winter conditions change within hours; a clear reading "
               "this morning says nothing about this afternoon.",
               weather_sensitive=True),
        )},
    "bike_pump": {
        "label_en": "Public bicycle pump",
        "observations": (
            _o("works", "Pump works", "works", _TROG, 43200.0,
               "Tested by the contributor on their own tyre, if at "
               "all — pressure was not measured."),
            _o("hose_condition", "Hose condition", "condition", _TROG,
               43200.0,
               "Visible condition only: a hose that leaks under "
               "pressure looks intact at rest."),
        )},
    "public_toilet": {
        "label_en": "Public toilet",
        "observations": (
            _o("open", "Open", "works", _DAGSFARSK, 1440.0,
               "Open at that moment. Opening hours are the operator's "
               "record, not ours."),
            _o("cleanliness", "Cleanliness", "condition", _DAGSFARSK,
               1440.0,
               "A band set by eye, and eyes differ. Comparable over "
               "time at the same site."),
            _o("supplies", "Supplies present", "works", _DAGSFARSK,
               1440.0,
               "Observed at the dispenser at that moment — a full "
               "dispenser empties in an hour of use."),
        )},
    "harbour_berth": {
        "label_en": "Harbour berth",
        "observations": (
            _o("free_berths", "Free berths", "count", _DAGSFARSK, 720.0,
               "Counted from the quay; berths hidden behind a vessel "
               "are not counted as free."),
            _o("dock_condition", "Dock condition", "condition", _TROG,
               43200.0,
               "Above the waterline only. Nothing here says anything "
               "about the structure below it."),
        )},
    "beach": {
        "label_en": "Public beach",
        "observations": (
            _o("crowding", "Crowding", "condition", _FLYKTIG, 180.0,
               "A band set by eye at one moment on one stretch.",
               weather_sensitive=True),
            _o("litter", "Litter", "condition", _DAGSFARSK, 2880.0,
               "A band set by eye on one stretch of shore — a clean "
               "reading says nothing about the next bay."),
            _o("facilities_work", "Facilities working", "works", _TROG,
               43200.0,
               "Observed from outside, not tested — a tap that runs "
               "may still run cold or brown."),
        )},
}

# ── Färskhetslägen ─────────────────────────────────────────────────────
FRESHNESS = ("current", "ageing", "stale", "never")

# Triggers som DATA. En ny utlösare är en rad, inte en gren i koden.
TRIGGERS: dict[str, dict] = {
    "cadence": {"label_en": "On a fixed cadence",
                "params_en": "every (hourly|daily|weekly), at (HH:MM)",
                "cannot_en": "A cadence cannot know that something "
                             "happened between two runs."},
    "not_verified_for": {
        "label_en": "When nothing has been verified for too long",
        "params_en": "minutes",
        "cannot_en": "This fires on OUR silence, which is not the same "
                     "as the world being unchanged."},
    "after_event": {
        "label_en": "After a scheduled event ends",
        "params_en": "event_ref, delay_minutes",
        "cannot_en": "The event calendar is the customer's; we cannot "
                     "see that an event ran long."},
    "after_weather": {
        "label_en": "After heavy rain or snowfall",
        "params_en": "kind (rain|snow), threshold, window_hours",
        "cannot_en": "Weather comes from the harvested open source for "
                     "the nearest point — a downpour two blocks away "
                     "may not register, and one that did register may "
                     "not have reached this site."},
}


class ObservationRefused(ValueError):
    """Observationen gick inte att registrera, och varför."""


def _spec(kind: str, obs_id: str) -> dict:
    typ = OBJECT_TYPES.get(kind)
    if typ is None:
        raise ObservationRefused(
            f"unknown object type {kind!r}; choose "
            f"{', '.join(sorted(OBJECT_TYPES))}")
    for o in typ["observations"]:
        if o["id"] == obs_id:
            return o
    raise ObservationRefused(
        f"{kind!r} has no observation {obs_id!r}; it observes "
        f"{', '.join(o['id'] for o in typ['observations'])}")


def _validate_value(spec: dict, value) -> object:
    k = spec["kind"]
    if k == "count":
        if not isinstance(value, (int, float)) or value < 0:
            raise ObservationRefused(
                f"{spec['id']} is a count and needs a number ≥ 0, got "
                f"{value!r}")
        return int(value)
    if k == "ratio":
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ObservationRefused(
                f"{spec['id']} is a share of capacity and needs 0–1, "
                f"got {value!r}")
        return float(value)
    if k == "works":
        if not isinstance(value, bool):
            raise ObservationRefused(
                f"{spec['id']} is working/not working and needs a "
                f"boolean, got {value!r}")
        return value
    if value not in CONDITION_BANDS:
        raise ObservationRefused(
            f"{spec['id']} is a condition band and needs one of "
            f"{', '.join(CONDITION_BANDS)}, got {value!r}")
    return value


def observe(object_id: str, kind: str, values: dict, *,
            mission_id: str = "", observer_network: str = "quixzoom",
            tenant: str = "", observed_at: float = 0.0) -> dict:
    """Registrera EN verifierad observation av ett objekt.

    `mission_id` är obligatoriskt: en observation utan uppdragsreferens
    går inte att knyta till sitt bevis, och en observation utan bevis är
    ett påstående. Bilden lagras aldrig här — den bor hos quiXzoom.
    """
    if not object_id:
        raise ObservationRefused("an observation needs an object_id")
    if not mission_id:
        raise ObservationRefused(
            "an observation without a mission_id cannot be tied to its "
            "evidence, and an observation without evidence is an "
            "assertion. The photograph stays with quiXzoom; this is its "
            "reference.")
    if not values:
        raise ObservationRefused(
            "an observation with no values recorded nothing — a visit "
            "is not an observation")
    rena = {}
    for oid, v in values.items():
        rena[oid] = _validate_value(_spec(kind, oid), v)
    return {"id": uuid.uuid4().hex[:12], "object_id": object_id,
            "kind": kind, "values": rena, "mission_id": mission_id,
            "observer_network": observer_network, "tenant": tenant,
            "observed_at": float(observed_at) or _time.time()}


# ── Färskheten: modulens hela poäng ────────────────────────────────────
def _freshness(spec: dict, alder_min: float) -> str:
    if alder_min <= spec["fresh_minutes"]:
        return "current"
    if alder_min <= spec["stale_minutes"]:
        return "ageing"
    return "stale"


def _band(observationer: list[dict], oid: str) -> dict:
    """Tillförlitlighet som BAND, aldrig som poäng.

    Räknas på oberoende NÄT som sett samma fält — samma regel som resten
    av plattformen. En ensam observatör kan aldrig nå över `weak`,
    hur många gånger hen än tittat.
    """
    nat = [{"sensor_class": "field_observation",
            "network": o.get("observer_network") or "quixzoom",
            "measured": True}
           for o in observationer if oid in o["values"]]
    if not nat:
        return {"band": "none", "networks": 0, "observations": 0}
    k = corroborate(nat)
    return {"band": k["strength"], "networks": k.get("independent", 1),
            "observations": len(nat)}


def status(object_id: str, kind: str, observations: list[dict], *,
           now: float = 0.0) -> dict:
    """Objektets läge — fält för fält, med färskheten som spärr.

    Ett utgånget flyktigt värde presenteras som HISTORIK med sin ålder,
    aldrig som status. Ingenting uppskattas mellan observationer.
    """
    if kind not in OBJECT_TYPES:
        raise ObservationRefused(f"unknown object type {kind!r}")
    nu = now or _time.time()
    mina = sorted((o for o in observations if o["object_id"] == object_id),
                  key=lambda o: -o["observed_at"])
    falt = []
    for spec in OBJECT_TYPES[kind]["observations"]:
        senaste = next((o for o in mina if spec["id"] in o["values"]), None)
        if senaste is None:
            falt.append({
                "observation_id": spec["id"], "label_en": spec["label_en"],
                "kind": spec["kind"], "freshness": "never",
                "value": None, "observed_at": None, "age_minutes": None,
                "confidence": {"band": "none", "networks": 0,
                               "observations": 0},
                "cannot_en": spec["cannot_en"],
                "why_en": ("Never verified. No value is estimated for "
                           "it — an estimated figure looks exactly like "
                           "a measured one.")})
            continue
        alder = (nu - senaste["observed_at"]) / 60.0
        lage = _freshness(spec, alder)
        rad = {
            "observation_id": spec["id"], "label_en": spec["label_en"],
            "kind": spec["kind"], "freshness": lage,
            "observed_at": senaste["observed_at"],
            "age_minutes": round(alder, 1),
            "fresh_for_minutes": spec["fresh_minutes"],
            "confidence": _band(mina, spec["id"]),
            "mission_id": senaste.get("mission_id", ""),
            "cannot_en": spec["cannot_en"],
        }
        if lage == "stale":
            # Det avgörande valet i hela modulen: värdet flyttas ur
            # `value` och in i `last_known` — en integration som läser
            # `value` kan därmed INTE råka visa en utgången färskvara
            # som nuläge.
            rad["value"] = None
            rad["last_known"] = senaste["values"][spec["id"]]
            rad["why_en"] = (
                f"Last verified {round(alder)} min ago; this field stops "
                f"being a statement about now after "
                f"{round(spec['stale_minutes'])} min. The last known "
                f"value is kept as history under 'last_known' — it is "
                f"not the current state, and nothing was estimated to "
                f"fill the gap.")
        else:
            rad["value"] = senaste["values"][spec["id"]]
            rad["why_en"] = (
                f"Verified {round(alder)} min ago"
                + ("." if lage == "current" else
                   f" — past its {round(spec['fresh_minutes'])} min "
                   f"freshness window, so it is usable WITH its age, "
                   f"not as a statement about this minute."))
        falt.append(rad)

    aktuella = [f for f in falt if f["freshness"] == "current"]
    return {
        "object_id": object_id, "kind": kind,
        "kind_label_en": OBJECT_TYPES[kind]["label_en"],
        "fields": falt,
        "current_fields": len(aktuella),
        "of_fields": len(falt),
        "last_verified": mina[0]["observed_at"] if mina else None,
        "observation_count": len(mina),
        "what_en": ("Field-by-field state from verified field "
                    "observations, each with its age and how long that "
                    "kind of value stays current."),
        "cannot_en": (
            "Nothing here is estimated, interpolated or modelled: a "
            "field is either verified within its freshness window, "
            "verified longer ago (usable with its age), or not a "
            "statement about now at all. Confidence is a BAND, never a "
            "score — a figure like '84% certain' invites being "
            "multiplied onward into calculations it cannot carry."),
    }


def freshness_record(object_id: str, kind: str,
                     observations: list[dict], *,
                     now: float = 0.0) -> dict:
    """Reality Freshness: när, hur ofta, hur väl underbyggt — och när
    objektet bör ses igen."""
    s = status(object_id, kind, observations, now=now)
    nu = now or _time.time()
    forfaller = []
    for f in s["fields"]:
        spec = _spec(kind, f["observation_id"])
        if f["observed_at"] is None:
            forfaller.append((0.0, f["observation_id"]))
            continue
        nasta = f["observed_at"] + spec["fresh_minutes"] * 60.0
        forfaller.append((max(0.0, (nasta - nu) / 60.0),
                          f["observation_id"]))
    forfaller.sort()
    band = [f["confidence"]["band"] for f in s["fields"]
            if f["confidence"]["band"] != "none"]
    return {
        "object_id": object_id, "kind": kind,
        "last_verified": s["last_verified"],
        "observation_count": s["observation_count"],
        "current_fields": s["current_fields"], "of_fields": s["of_fields"],
        "confidence_bands": sorted(set(band)) or ["none"],
        "next_check_due_in_minutes": round(forfaller[0][0], 1)
        if forfaller else None,
        "next_check_driven_by": forfaller[0][1] if forfaller else None,
        "why_en": (
            "The next check is driven by the FASTEST-perishing field on "
            "this object, not by an average: a site whose occupancy "
            "expires in 20 minutes needs seeing again in 20 minutes, "
            "however fresh its signage reading is."),
        "cannot_en": (
            "Frequency is not accuracy. Verifying a site every hour "
            "with one contributor still leaves every field capped at "
            "the 'weak' band — one observer cannot corroborate "
            "themselves, however often they look."),
    }


def due(objects: list[dict], observations: list[dict], *,
        now: float = 0.0, triggers: list[dict] | None = None) -> dict:
    """Vad som behöver ses igen nu — och varför just det."""
    nu = now or _time.time()
    forfallna, aldrig = [], []
    for obj in objects:
        kind = obj.get("kind", "")
        if kind not in OBJECT_TYPES:
            continue
        fr = freshness_record(obj["id"], kind, observations, now=nu)
        rad = {"object_id": obj["id"], "kind": kind,
               "label_en": obj.get("label_en") or obj["id"],
               "lat": obj.get("lat"), "lon": obj.get("lon"),
               "driven_by": fr["next_check_driven_by"],
               "overdue_minutes": round(-fr["next_check_due_in_minutes"], 1)
               if fr["next_check_due_in_minutes"] is not None
               and fr["next_check_due_in_minutes"] <= 0 else 0.0}
        if fr["last_verified"] is None:
            aldrig.append(rad)
        elif (fr["next_check_due_in_minutes"] or 0) <= 0:
            forfallna.append(rad)
    utlosare = [t for t in (triggers or [])
                if t.get("kind") in TRIGGERS]
    okanda = [t.get("kind") for t in (triggers or [])
              if t.get("kind") not in TRIGGERS]
    if okanda:
        raise ObservationRefused(
            f"unknown trigger kind(s) {okanda}; choose "
            f"{', '.join(sorted(TRIGGERS))}")
    return {
        "due": forfallna, "never_verified": aldrig,
        "due_count": len(forfallna), "never_count": len(aldrig),
        "triggers_applied": [t["kind"] for t in utlosare],
        "quiet_en": ("Nothing is due: every object has been verified "
                     "inside its fastest field's window. That is a "
                     "result, not an empty answer."
                     if not forfallna and not aldrig else ""),
        "cannot_en": ("Being due is about OUR silence, not about the "
                      "world having changed. A site can go wrong one "
                      "minute after a perfect verification, and no "
                      "schedule can see that."),
    }


def sla_report(objects: list[dict], observations: list[dict], *,
               promised_minutes: float, window_hours: float = 168.0,
               now: float = 0.0) -> dict:
    """Höll den utlovade kontrollfrekvensen? Räknat ur HISTORIKEN.

    En SLA som redovisas ur avtalet i stället för ur körningarna är en
    utfästelse med en siffra på. Det här räknar de faktiska gapen.
    """
    if promised_minutes <= 0:
        raise ObservationRefused("promised_minutes must be positive")
    nu = now or _time.time()
    fran = nu - window_hours * 3600.0
    rader, brott = [], 0
    for obj in objects:
        tider = sorted(o["observed_at"] for o in observations
                       if o["object_id"] == obj["id"]
                       and o["observed_at"] >= fran)
        gap = []
        forra = fran
        for t in tider:
            gap.append((t - forra) / 60.0)
            forra = t
        gap.append((nu - forra) / 60.0)          # gapet fram till nu
        varsta = max(gap) if gap else 0.0
        holl = varsta <= promised_minutes
        if not holl:
            brott += 1
        rader.append({"object_id": obj["id"],
                      "verifications": len(tider),
                      "worst_gap_minutes": round(varsta, 1),
                      "met": holl})
    return {
        "promised_minutes": promised_minutes,
        "window_hours": window_hours,
        "objects": len(objects), "breaches": brott,
        "met": brott == 0,
        "rows": sorted(rader, key=lambda r: -r["worst_gap_minutes"]),
        "measured_en": ("Computed from the actual observation history in "
                        "the window — the worst gap between two "
                        "verifications, including the open gap up to "
                        "now. Not read from the contract."),
        "cannot_en": ("It measures whether someone LOOKED often enough, "
                      "never whether what they saw was right. A "
                      "perfectly met SLA on a single observer network "
                      "still leaves every field at the 'weak' band."),
    }


def fields_to_verify(object_id: str, kind: str,
                     observations: list[dict], *,
                     now: float = 0.0) -> list[dict]:
    """Fälten vars färskhetsfönster passerat (eller aldrig setts) —
    det uppdraget ska be zoomern titta på."""
    s = status(object_id, kind, observations, now=now)
    ut = []
    for f in s["fields"]:
        if f["freshness"] == "never" or (
                f["age_minutes"] is not None
                and f["age_minutes"] > f.get("fresh_for_minutes", 0)):
            ut.append({"id": f["observation_id"],
                       "label_en": f["label_en"]})
    return ut


def mission_spec(obj: dict, observations: list[dict], *,
                 audience: dict | None = None,
                 weather_invalidated: bool = False,
                 now: float = 0.0) -> dict:
    """Rut-formad specifikation för quixzoom_dispatch.dispatch().

    ÅTERBRUK, inte ny transportkod: MissionDispatcher läser `label_en`,
    `checks` och `audience` ur en rutin-dict — den här bygger samma form
    ur objektets förfallna fält, så uppdragsloopen går genom exakt samma
    beställningsväg (och samma vägransregler) som fotokontrollerna.

    `weather_invalidated`: regn/snöfall ogiltigförklarar de
    väderkänsliga fälten genom HÄNDELSEN, inte klockan — de tas med i
    uppdraget även om deras avläsning är minuter gammal.
    """
    kind = obj.get("kind", "")
    if kind not in OBJECT_TYPES:
        raise ObservationRefused(f"unknown object type {kind!r}")
    falt = fields_to_verify(obj["id"], kind, observations, now=now)
    if weather_invalidated:
        redan = {f["id"] for f in falt}
        falt += [{"id": o["id"], "label_en": o["label_en"]}
                 for o in OBJECT_TYPES[kind]["observations"]
                 if o.get("weather_sensitive") and o["id"] not in redan]
    if not falt:
        raise ObservationRefused(
            f"nothing on {obj['id']} needs verifying — every field is "
            f"inside its freshness window, and ordering a mission "
            f"anyway would bill the customer for looking at nothing")
    return {"id": f"infra-{obj['id']}",
            "label_en": f"Verify {OBJECT_TYPES[kind]['label_en'].lower()}",
            "checks": tuple(f["label_en"] for f in falt),
            "audience": audience or {"pool": "open"}}


def weather_trigger_met(trigger: dict, lat: float | None,
                        lon: float | None, *, now: float = 0.0) -> dict:
    """Utvärdera `after_weather` mot SKÖRDAT väder — aldrig ett anrop.

    Utan en skördad väderrad inom räckhåll utlöses triggern INTE, med
    skälet: en blind trigger får inte avfyra, och vår tystnad är inte
    ett väder. Snö är ett NÄRMEVÄRDE (nederbörd vid ≤ 0 °C) och sägs
    vara det.
    """
    from engine import harvest

    p = trigger.get("params") or {}
    slag = p.get("kind", "rain")
    troskel = float(p.get("threshold", 5.0))
    if lat is None or lon is None:
        return {"met": False,
                "why_en": "the object has no coordinates, so no weather "
                          "reading can be matched to it"}
    rader = harvest.read("open_meteo", lat, lon,
                         ["precipitation_mm", "air_temperature_c"],
                         now=now)
    nederbord = rader.get("precipitation_mm")
    if nederbord is None:
        return {"met": False,
                "why_en": "no harvested weather within reach of this "
                          "object — a blind trigger must not fire, and "
                          "our silence is not weather"}
    mm = float(nederbord.get("value") or 0)
    if slag == "snow":
        temp = rader.get("air_temperature_c")
        if temp is None:
            return {"met": False,
                    "why_en": "snow needs a temperature reading beside "
                              "the precipitation, and none is harvested "
                              "within reach"}
        kallt = float(temp.get("value") or 99) <= 0.0
        return {"met": mm >= troskel and kallt,
                "why_en": (f"{mm} mm precipitation at "
                           f"{temp.get('value')} °C — snow here is a "
                           f"PROXY (precipitation at or below zero), "
                           f"not an observed snowfall.")}
    return {"met": mm >= troskel,
            "why_en": f"{mm} mm harvested precipitation against the "
                      f"{troskel} mm threshold "
                      f"({nederbord.get('age_days')} day(s) old, "
                      f"{nederbord.get('distance_km')} km away)."}


def catalog() -> dict:
    return {
        "what_en": ("Recurring verification of physical objects by field "
                    "observation, with freshness as a first-class "
                    "property: every value states how long that KIND of "
                    "value stays current, and an expired perishable is "
                    "served as history rather than as status."),
        "object_types": [
            {"id": tid, "label_en": t["label_en"],
             "observations": [
                 {k: v for k, v in o.items()} for o in t["observations"]]}
            for tid, t in OBJECT_TYPES.items()],
        "observation_kinds": OBS_KINDS,
        "condition_bands": list(CONDITION_BANDS),
        "freshness_states": list(FRESHNESS),
        "triggers": TRIGGERS,
        "pricing_note_en": ("What a customer buys here is VERIFIED "
                            "observation, not a live sensor feed and "
                            "not an estimate. The difference is stated "
                            "on every field, so nobody buys the wrong "
                            "thing by accident."),
        "cannot_en": ("This is not a sensor network and not an "
                      "inspection authority. It cannot see what a "
                      "photograph cannot show, it estimates nothing "
                      "between visits, and its confidence is a band "
                      "because a percentage would be multiplied onward "
                      "into calculations it cannot carry."),
    }
