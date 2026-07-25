"""Anslutnings-cockpit – varje datakälla, dess live/mock-läge och hur den slås på.

Gör "koppla allt skarpt" operabelt: en enda vy över alla adaptrar med den
env-var som aktiverar var och en. Sätt variabeln (i en nätverkstillåten miljö)
→ motorn använder källan automatiskt och degraderar ärligt till märkt mock
annars. Ren stdlib (bara os.environ + adaptrarnas connected-flagga).
"""
from __future__ import annotations

import os

# Varje adapter: id, namn, env-var som pekar den mot en live-endpoint, vad den
# levererar, och den officiella källan bakom den.
ADAPTERS: tuple[dict, ...] = (
    {"id": "scb", "name": "SCB (Statistics Sweden)", "env": "LANDVEX_SCB_BASE",
     "provides": ["pop_growth_pct", "income_index", "age_20_45_share",
                  "share_65plus", "population_total"],
     "official": "SCB PxWeb (doris)", "default_on": True},
    {"id": "kolada", "name": "Kolada", "env": "LANDVEX_KOLADA_URL",
     "provides": ["life_expectancy", "excess_mortality", "violent_crime_rate",
                  "school_outcomes_grade9", "healthcare_queue_functional"],
     "official": "Kolada v2 (SSYK/municipal KPIs)", "default_on": False},
    {"id": "svk", "name": "Svenska Kraftnät / ENTSO-E", "env": "LANDVEX_SVK_URL",
     "provides": ["production_mix", "stability_score", "balance_mw"],
     "official": "SVK controlroom / ENTSO-E", "default_on": False},
    {"id": "permits", "name": "Building permits / detail plans",
     "env": "LANDVEX_PERMITS_URL",
     "provides": ["building_permits", "detail_plans", "development_m2"],
     "official": "Municipal open data / Boverket", "default_on": False},
    {"id": "places", "name": "Places / competition", "env": "LANDVEX_PLACES_URL",
     "provides": ["competition_pressure", "provider_gap"],
     "official": "Places aggregator (Google/OSM)", "default_on": False},
    {"id": "programs", "name": "Support programs registry",
     "env": "LANDVEX_PROGRAMS_URL", "provides": ["support_programs"],
     "official": "EU Funding & Tenders / Vinnova / regional funds",
     "default_on": False},
    {"id": "quixzoom", "name": "quiXzoom field observations",
     "env": "LANDVEX_QUIXZOOM_URL", "alt_env": "AAMOS_CORE_URL",
     "provides": ["field_observation_density"],
     "official": "quiXzoom via AAMOS Core (:3100) or direct (:3209)",
     "default_on": False},
    {"id": "aamos", "name": "AAMOS Capability Platform", "env": "AAMOS_CORE_URL",
     "provides": ["platform_status", "agents", "cognition"],
     "official": "AAMOS Core (service-account token)", "default_on": False},
    {"id": "registers", "name": "Business registers (EU NACE / US NAICS)",
     "env": "LANDVEX_REGISTER_URL",
     "provides": ["establishment counts by industry and region"],
     "official": "SCB/Bolagsverket, Destatis, INSEE SIRENE, INE, ISTAT, "
                 "KVK, CVR, Br\u00f8nn\u00f8ysund, GUS, US Census CBP/QCEW",
     "default_on": False},
    {"id": "geo", "name": "Municipal register mirror", "env": "LANDVEX_GEO_URL",
     "provides": ["admin level 2: counties / kommuner / communes"],
     "official": "US Census FIPS / SCB kommunkod / StatCan SGC / INSEE COG",
     "default_on": False},
)


def sources_status() -> dict:
    """Alla adaptrar med konfigurationsläge + hur var och en kopplas skarpt."""
    out = []
    live = 0
    for a in ADAPTERS:
        configured = bool(os.environ.get(a["env"], "").strip()) \
            or bool(os.environ.get(a.get("alt_env", ""), "").strip()) \
            or a.get("default_on", False)
        if configured and a["id"] != "scb":
            live += 1
        elif a["id"] == "scb":
            live += 1 if configured else 0
        env_hint = a["env"] + ("  (or " + a["alt_env"] + ")"
                               if a.get("alt_env") else "")
        out.append({
            "id": a["id"], "name": a["name"], "state": "live" if configured else "mock",
            "activate_with": env_hint, "provides": a["provides"],
            "official_source": a["official"],
        })
    return {
        "sources": out, "live": live, "total": len(ADAPTERS),
        "note": "Set a source's env var (in a network-allowed environment) to "
                "connect it live; the engine uses it automatically and degrades "
                "to labelled mock otherwise. Verify first with the probes in "
                "scripts/ (kolada_probe, svk_probe, scb_probe, aamos_smoke).",
    }
