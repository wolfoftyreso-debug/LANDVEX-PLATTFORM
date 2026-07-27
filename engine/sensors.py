"""Sensorer — vad som faktiskt kan MÄTA det briefen letar efter.

Upptäcktslagret (`engine/brief.DETECTION_KINDS`) kan känna igen nio
sorters fysisk förändring: en byggd yta som ändrats, ett flöde som
avviker, ett objekt som försvunnit, en kondition som faller snabbare än
hos jämförbara. Det är sensorformulerat rakt igenom.

Källorna som är inkopplade är statistik och register: SCB, Kolada,
Eurostat, bygglov, företagsregister. De uppdateras kvartalsvis eller
årsvis och beskriver vad som ALLTS har hänt. Två undantag finns —
elnätet (SVK/ENTSO-E) och fältobservationerna (quiXzoom) — men resten av
upptäcktslagret har ingenting som matar det.

Registret här stänger inte den luckan. Det NAMNGER den, per
upptäcktstyp, så att skillnaden mellan "vi kan upptäcka det" och "vi kan
mäta det" står i klartext i stället för att antas åt fel håll.

Varje sensorklass deklarerar fyra saker, och den tredje är den viktiga:

    feeds          vilka upptäcktstyper den kan mata
    cadence        hur ofta den säger något nytt
    cannot_en      vad den ALDRIG kan avgöra, hur tät den än är
    connected_by   miljövariabeln som kopplar in den

`cannot_en` finns för att sensordata frestar värre än statistik. En
mätning varje minut känns som kunskap, men en trafikräknare som visar
fyrtio procent mindre flöde vet inte om det beror på en avstängd väg,
en flyttad arbetsgivare eller en trasig slinga. Frekvens är inte
förståelse, och ett larm som inte vet det blir ett larm man slutar läsa.

Rent stdlib. Allt är data: en ny sensorklass är en rad, ingen
motorändring.
"""
from __future__ import annotations

# state: connected  = en adapter finns OCH kan slås på med connected_by
#        adapter    = adapter finns, källan ej verifierad live
#        none       = ingenting byggt; upptäckten har inget som matar den
SENSORS: dict[str, dict] = {
    "grid_telemetry": {
        "label_en": "Electricity grid telemetry",
        "what_en": "Production mix, frequency balance and transfer between "
                   "bidding zones, read from the transmission operator.",
        "feeds": ("energy_change", "pattern_deviation"),
        "cadence": "minutes",
        "typical_lag": "5–15 min",
        "cannot_en": "Attribute a change to any single consumer or site. The "
                     "signal is a zone aggregate; a factory starting up and a "
                     "wind lull move it the same way.",
        "state": "adapter",
        "connected_by": "LANDVEX_SVK_URL",
        "operator_en": "Svenska kraftnät · ENTSO-E Transparency Platform",
        "open_data": True,
    },
    "field_observation": {
        "label_en": "Field observations (camera-first)",
        "what_en": "Time- and place-stamped observations captured by people "
                   "on site, through quiXzoom.",
        "feeds": ("structure_change", "new_activity", "object_new",
                  "object_gone", "infrastructure_decay"),
        "cadence": "irregular",
        "typical_lag": "minutes to weeks",
        "cannot_en": "Establish coverage. Observations appear where people "
                     "go, so an absence of observations is not an absence of "
                     "change — it is an absence of observers.",
        "state": "adapter",
        "connected_by": "LANDVEX_QUIXZOOM_URL",
        "operator_en": "quiXzoom field platform",
        "open_data": False,
    },
    "road_flow": {
        "label_en": "Road traffic counters",
        "what_en": "Vehicle counts and average speed per measurement point "
                   "on the state road network.",
        "feeds": ("traffic_shift", "pattern_deviation"),
        "cadence": "minutes",
        "typical_lag": "5–60 min",
        "cannot_en": "Say WHY flow changed. A closure, a new employer and a "
                     "failed loop detector all look identical in the count.",
        "state": "adapter",
        "connected_by": "LANDVEX_TRAFFIC_URL (+ LANDVEX_TRAFFIC_KEY)",
        "operator_en": "Trafikverket (SE) · national road authorities (EU)",
        "open_data": True,
    },
    "weather": {
        "label_en": "Weather stations",
        "what_en": "Temperature, precipitation, wind and snow depth from the "
                   "national observation network.",
        "feeds": ("pattern_deviation",),
        "cadence": "hourly",
        "typical_lag": "1–2 h",
        "cannot_en": "Explain an economic change on its own. Weather is a "
                     "confounder for almost every outdoor measurement, which "
                     "makes it most useful for RULING OUT a cause rather "
                     "than establishing one.",
        "state": "adapter",
        "connected_by": "LANDVEX_WEATHER_URL",
        "operator_en": "SMHI (SE) · national meteorological services",
        "open_data": True,
    },
    "air_quality": {
        "label_en": "Air quality monitors",
        "what_en": "NO₂, PM10 and PM2.5 at fixed urban measurement stations.",
        "feeds": ("traffic_shift", "pattern_deviation"),
        "cadence": "hourly",
        "typical_lag": "1–24 h",
        "cannot_en": "Localise a source. A station measures its own street "
                     "canyon, and wind moves the plume; the reading is not a "
                     "map of who emitted what.",
        "state": "none",
        "connected_by": "LANDVEX_AIR_URL",
        "operator_en": "Naturvårdsverket / SLB-analys (SE) · EEA (EU)",
        "open_data": True,
    },
    "earth_observation": {
        "label_en": "Satellite imagery",
        "what_en": "Repeat optical and radar coverage used to compare the "
                   "same parcel between two dates.",
        "feeds": ("structure_change", "land_use_change", "object_new",
                  "object_gone"),
        "cadence": "days",
        "typical_lag": "1–5 days",
        "cannot_en": "See through cloud in the optical bands, or establish "
                     "that a change is unpermitted. A difference between two "
                     "images is a difference between two images.",
        "state": "none",
        "connected_by": "LANDVEX_EO_URL",
        "operator_en": "Copernicus Sentinel-1/2 (ESA, open)",
        "open_data": True,
    },
    "building_meter": {
        "label_en": "Building energy meters",
        "what_en": "District heating and electricity consumption per "
                   "property, where the owner shares it.",
        "feeds": ("energy_change", "infrastructure_decay",
                  "pattern_deviation"),
        "cadence": "hourly",
        "typical_lag": "1 day",
        "cannot_en": "Be read across owners without consent. Consumption at "
                     "building level is close to personal data when the "
                     "building is small.",
        "state": "none",
        "connected_by": "LANDVEX_METER_URL",
        "operator_en": "Property owners · district heating utilities",
        "open_data": False,
    },
    "mobility_flow": {
        "label_en": "Aggregated movement data",
        "what_en": "Anonymised, aggregated presence and travel between "
                   "areas, from mobile network or app panels.",
        "feeds": ("traffic_shift", "new_activity", "pattern_deviation"),
        "cadence": "daily",
        "typical_lag": "1–7 days",
        "cannot_en": "Be treated as a population count. Panels are biased by "
                     "who carries what, and small cells are suppressed — the "
                     "same k-anonymity floor that gates sensitive questions "
                     "applies here.",
        "state": "none",
        "connected_by": "LANDVEX_MOVEMENT_URL",
        "operator_en": "Mobile operators · mobility data vendors",
        "open_data": False,
    },
}

# Upptäcktstyper som INGEN sensorklass ovan kan mata. Tom lista betyder
# inte "klart" — det betyder att varje upptäckt har minst en tänkbar
# mätare, inte att den är inkopplad.
def unfed_detections() -> list[str]:
    """Upptäckter som ingen sensorklass i registret ens skulle kunna mata."""
    from .brief import DETECTION_KINDS
    matade = {d for s in SENSORS.values() for d in s["feeds"]}
    return sorted(set(DETECTION_KINDS) - matade)


def sensors_for(detection_kind: str) -> list[dict]:
    """Vilka sensorklasser som kan mata en viss upptäckt."""
    return [{"id": sid, **{k: v for k, v in s.items() if k != "feeds"},
             "feeds": list(s["feeds"])}
            for sid, s in SENSORS.items() if detection_kind in s["feeds"]]


def catalog() -> dict:
    """Sensorlandskapet: vad som kan mätas, vad som är inkopplat, och vad
    varje mätning aldrig kan avgöra."""
    from .brief import DETECTION_KINDS
    rader = [{"id": sid, **{k: v for k, v in s.items() if k != "feeds"},
              "feeds": list(s["feeds"])}
             for sid, s in SENSORS.items()]
    per_state: dict[str, int] = {}
    for s in SENSORS.values():
        per_state[s["state"]] = per_state.get(s["state"], 0) + 1
    tackning = {k: [s["id"] for s in rader if k in SENSORS[s["id"]]["feeds"]]
                for k in DETECTION_KINDS}
    return {
        "sensors": rader,
        "count": len(rader),
        "by_state": per_state,
        "detection_coverage": tackning,
        "unfed_detections": unfed_detections(),
        "gap_en": (
            f"{per_state.get('adapter', 0)} of {len(rader)} sensor classes "
            f"have an adapter written; {per_state.get('none', 0)} have "
            f"nothing built. The detection layer recognises "
            f"{len(DETECTION_KINDS)} kinds of physical change, and most of "
            f"them are currently fed by statistics that update quarterly. "
            f"That is a real limit on what the platform can notice, and it "
            f"is stated rather than left to be assumed."),
        "why_cannot_matters_en": (
            "Every class declares what it can NEVER establish. Sensor data "
            "tempts worse than statistics: a reading every minute feels like "
            "knowledge, but a counter showing forty percent less flow does "
            "not know whether a road closed, an employer moved, or the loop "
            "broke. Frequency is not understanding, and an alert that does "
            "not know the difference becomes an alert nobody reads."),
        "open_data_share": round(
            sum(1 for s in SENSORS.values() if s["open_data"]) / len(SENSORS),
            2),
        "clients": _client_status(),
    }


def _client_status() -> list[dict]:
    """Vad de byggda klienterna säger om sig själva just nu."""
    from .datasources.sensor_apis import clients_status
    return clients_status()
