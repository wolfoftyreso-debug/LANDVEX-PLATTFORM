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
#        adapter    = adapter mot ett publikt API finns, ej verifierad live
#        contract   = inget publikt API existerar, men det finns en
#                     dokumenterad form en ägare kan leverera IN i
#                     (GenericSensorFeed). Skillnaden mot `adapter` är
#                     inte kosmetisk: här väntar vi på ett AVTAL, inte på
#                     en nyckel, och det är en helt annan sorts arbete.
#        none       = ingenting byggt
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
        "state": "adapter",
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
        "state": "adapter",
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
        "state": "contract",
        "connected_by": "LANDVEX_METER_URL",
        "operator_en": "Property owners · district heating utilities",
        "open_data": False,
    },
    "water_level": {
        "label_en": "Water level and flow",
        "what_en": "River and lake levels, discharge, and groundwater "
                   "levels from the national hydrological network.",
        "feeds": ("pattern_deviation", "infrastructure_decay"),
        "cadence": "hourly",
        "typical_lag": "1–3 h",
        "cannot_en": "Predict flooding at a specific address. A gauge "
                     "measures its own cross-section; what reaches a "
                     "basement depends on terrain, culverts and drains "
                     "that no water-level series contains.",
        "state": "adapter",
        "connected_by": "LANDVEX_HYDRO_URL",
        "operator_en": "SMHI hydrology · SGU groundwater (SE)",
        "open_data": True,
    },
    "public_transport": {
        "label_en": "Public transport vehicle positions",
        "what_en": "Live vehicle positions, delays and cancellations "
                   "published as GTFS-Realtime by the transit operator.",
        "feeds": ("traffic_shift", "pattern_deviation",
                  "infrastructure_decay"),
        "cadence": "seconds",
        "typical_lag": "10–60 s",
        "cannot_en": "Count passengers. A vehicle's position says where the "
                     "service is, not whether anyone is on it, and a full "
                     "bus and an empty one report identically.",
        "state": "none",
        "connected_by": "LANDVEX_TRANSIT_URL",
        "operator_en": "Regional transit authorities (GTFS-RT is a standard)",
        "open_data": True,
    },
    "vessel_traffic": {
        "label_en": "Ship movements (AIS)",
        "what_en": "Vessel identity, position, draught and destination "
                   "broadcast continuously by ships over AIS.",
        "feeds": ("traffic_shift", "new_activity", "pattern_deviation"),
        "cadence": "minutes",
        "typical_lag": "near real time",
        "cannot_en": "Establish cargo or ownership. AIS carries what the "
                     "crew entered; destination and draught are typed in "
                     "and are wrong often enough to matter.",
        "state": "adapter",
        "connected_by": "LANDVEX_AIS_URL",
        "operator_en": "Fintraffic Digitraffic (open) · coastal authorities",
        "open_data": True,
    },
    "district_heating": {
        "label_en": "District heating network",
        "what_en": "Supply temperature, flow and load per network section, "
                   "where the utility shares it.",
        "feeds": ("energy_change", "infrastructure_decay",
                  "pattern_deviation"),
        "cadence": "hourly",
        "typical_lag": "1–24 h",
        "cannot_en": "Separate a leak from a cold spell without weather "
                     "alongside it. Load follows outdoor temperature far "
                     "more strongly than it follows any fault.",
        "state": "contract",
        "connected_by": "LANDVEX_HEAT_URL",
        "operator_en": "District heating utilities",
        "open_data": False,
    },
    "water_utility": {
        "label_en": "Water and wastewater flows",
        "what_en": "Consumption per zone and inflow at treatment works — "
                   "the closest thing to a live occupancy signal a "
                   "municipality already owns.",
        "feeds": ("new_activity", "pattern_deviation",
                  "infrastructure_decay"),
        "cadence": "hourly",
        "typical_lag": "1 day",
        "cannot_en": "Be attributed to a household. Zone-level flow is an "
                     "aggregate, and making it finer turns it into "
                     "personal data about when people are home.",
        "state": "contract",
        "connected_by": "LANDVEX_WATER_URL",
        "operator_en": "Municipal water utilities",
        "open_data": False,
    },
    "waste_volume": {
        "label_en": "Waste collection volumes",
        "what_en": "Tonnage and pickup frequency per district — a lagging "
                   "but honest proxy for how much activity a place "
                   "actually carries.",
        "feeds": ("new_activity", "pattern_deviation"),
        "cadence": "weekly",
        "typical_lag": "1–4 weeks",
        "cannot_en": "Distinguish more people from more waste per person. "
                     "Tonnage rises for both, and only one of them means "
                     "the place is growing.",
        "state": "contract",
        "connected_by": "LANDVEX_WASTE_URL",
        "operator_en": "Municipal waste management",
        "open_data": False,
    },
    "parking_occupancy": {
        "label_en": "Parking occupancy",
        "what_en": "Occupied spaces per facility or street segment, from "
                   "barriers, sensors or payment systems.",
        "feeds": ("traffic_shift", "new_activity", "pattern_deviation"),
        "cadence": "minutes",
        "typical_lag": "minutes",
        "cannot_en": "Measure demand once a facility is full. A lot at "
                     "100% has been at 100% for an unknown margin, and the "
                     "queue outside it is invisible to the sensor.",
        "state": "contract",
        "connected_by": "LANDVEX_PARKING_URL",
        "operator_en": "Parking operators · municipalities",
        "open_data": False,
    },
    "construction_activity": {
        "label_en": "Construction site activity",
        "what_en": "Machine hours, deliveries and crane movement on active "
                   "sites, from telematics the contractor already collects.",
        "feeds": ("structure_change", "new_activity",
                  "pattern_deviation"),
        "cadence": "daily",
        "typical_lag": "1 day",
        "cannot_en": "Say whether the work is permitted or on schedule. "
                     "Activity is activity; the permit lives in a register "
                     "and the schedule lives in a contract.",
        "state": "contract",
        "connected_by": "LANDVEX_SITE_URL",
        "operator_en": "Contractors · equipment telematics vendors",
        "open_data": False,
    },
    "seismic": {
        "label_en": "Seismic events",
        "what_en": "Catalogued earthquakes above a magnitude threshold "
                   "within a radius, from the global seismic network.",
        "feeds": ("infrastructure_decay", "pattern_deviation"),
        "cadence": "minutes",
        "typical_lag": "2–20 min",
        "cannot_en": "Say anything about damage. A magnitude is energy at "
                     "the source; what a building does depends on distance, "
                     "soil and how it was built, none of which is in the "
                     "catalogue.",
        "state": "adapter",
        "connected_by": "LANDVEX_SEISMIC_URL",
        "operator_en": "USGS FDSN (open) · national seismic networks",
        "open_data": True,
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
        "state": "contract",
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
    from .corroboration import MODALITY
    from .datasources.sensor_apis import independent_count
    rader = [{"id": sid, **{k: v for k, v in s.items() if k != "feeds"},
              "feeds": list(s["feeds"]),
              # Hur många OBEROENDE nät som kan mäta klassen. Ett är ett;
              # två är det som gör att man kan tro på det.
              "independent_providers": independent_count(sid),
              "modality": MODALITY.get(sid, "unknown")}
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
            f"have an adapter against a public API; "
            f"{per_state.get('contract', 0)} have a documented shape an "
            f"owner can deliver into but no public API to build against; "
            f"{per_state.get('none', 0)} have nothing built. The detection layer recognises "
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
        "corroboration": _corroboration_summary(rader),
    }


def _corroboration_summary(rader: list[dict]) -> dict:
    """Vad som faktiskt gör underlaget robust: två oberoende nät, inte
    fler mätpunkter i samma."""
    tva_plus = [r["id"] for r in rader if r["independent_providers"] >= 2]
    return {
        "classes_with_two_or_more_providers": tva_plus,
        "count": len(tva_plus),
        "why_en": (
            "More sensors is not more robust. Ten points on the same road, "
            "from the same authority, through the same collection chain, "
            "fail together when the chain does. What raises the floor is a "
            "second INDEPENDENT network — and only these classes have one."),
        "detail": "/v1/corroboration",
    }


def _client_status() -> list[dict]:
    """Vad de byggda klienterna säger om sig själva just nu."""
    from .datasources.sensor_apis import clients_status
    return clients_status()
