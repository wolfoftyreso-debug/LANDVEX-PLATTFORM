"""Vad driftmiljön måste veta — och vad som händer när den inte vet det.

En miljövariabel som bara finns i en `os.environ`-rad är en inställning
ingen kan hitta förrän den saknas. Det här registret samlar alla, med den
enda rad som spelar roll vid en driftsättning: **vad händer om den inte
är satt?**

Tre nivåer:

    required     utan den startar systemet inte, eller startar osäkert
    recommended  systemet fungerar, men sämre eller mindre ärligt
    optional     en koppling till, inte en förutsättning

`secret: True` betyder att värdet aldrig får skrivas ut i klartext —
varken i preflight, loggar eller felmeddelanden. En hemlighet som läckt
i en startlogg är läckt.

Ett test i tests/test_deploy.py hävdar åt BÅDA håll: varje variabel koden
läser står här, och varje variabel som står här läses av koden. En
dokumentation som får glida ifrån verkligheten är sämre än ingen, för då
tror man på den.

Rent stdlib.
"""
from __future__ import annotations

import os


def _v(tier: str, purpose_en: str, if_unset_en: str, *,
       secret: bool = False, example: str = "") -> dict:
    return {"tier": tier, "purpose_en": purpose_en,
            "if_unset_en": if_unset_en, "secret": secret,
            "example": example}


ENVIRONMENT: dict[str, dict] = {
    # ── Kör och lyssna ───────────────────────────────────────────────
    "LANDVEX_PORT": _v(
        "recommended", "Port the API listens on.",
        "Defaults to 8000. Fine behind a load balancer that knows it.",
        example="8000"),
    "LANDVEX_HOST": _v(
        "recommended", "Interface to bind.",
        "Defaults to 0.0.0.0, which is right behind a load balancer and "
        "wrong on a laptop. Set 127.0.0.1 for local work.",
        example="0.0.0.0"),
    "LANDVEX_CORS_ORIGINS": _v(
        "optional", "Comma-separated origins allowed to call the API from "
                    "a browser.",
        "CORS middleware is not installed at all. Correct when the "
        "frontend is served from the same origin; breaks a separate "
        "frontend domain.",
        example="https://app.landvex.io"),

    # ── Persistens ───────────────────────────────────────────────────
    "LANDVEX_DB": _v(
        "required", "SQLite file for reports, profiles, decisions, "
                    "monitors and the monthly quota.",
        "Defaults to landvex.db in the working directory — which is "
        "ephemeral in a container. Every commitment, profile and quota "
        "count is lost on restart. Set a path on a mounted volume, or "
        "'off' to run stateless deliberately.",
        example="/data/landvex.db"),
    "LANDVEX_PG_DSN": _v(
        "recommended", "PostgreSQL connection string. Replaces SQLite in "
                       "production (Aurora + PostGIS).",
        "SQLite is used. One file, one writer: fine for a single task, "
        "wrong the moment a second replica starts, because the two "
        "cannot share it.",
        secret=True, example="postgresql://user:pass@host:5432/landvex"),

    # ── Säkerhet ─────────────────────────────────────────────────────
    "LANDVEX_API_KEYS": _v(
        "required", "Comma-separated key:tenant:role[:plan[:addons]] "
                    "entries.",
        "THE API RUNS OPEN. Every request is treated as an admin of "
        "tenant 'dev' with the enterprise plan. Acceptable on a laptop, "
        "never on a reachable host.",
        secret=True, example="k1:acme:analyst:pro,k2:beta:admin"),
    "LANDVEX_JWT_SECRET": _v(
        "recommended", "HS256 secret for bearer tokens (AAMOS standard).",
        "JWT authentication is disabled; a Bearer token is rejected with "
        "401. API keys still work.",
        secret=True),
    "LANDVEX_RATE_LIMIT": _v(
        "optional", "Global requests per minute per key.",
        "Defaults to 300. Per-plan limits still apply on top.",
        example="300"),
    "LANDVEX_AUDIT_LOG": _v(
        "recommended", "Path for the JSON-lines audit log.",
        "Defaults to landvex-audit.log in the working directory. Set "
        "'off' to disable, or a path outside a read-only /app.",
        example="/var/log/landvex/audit.jsonl"),

    # ── Källor: på eller av ──────────────────────────────────────────
    "LANDVEX_LIVE": _v(
        "recommended", "Set to 0 to disable every live source and run on "
                       "mock only.",
        "Live sources are attempted. That is right in production and "
        "wrong in CI, where it makes the build depend on third-party "
        "uptime.",
        example="1"),

    # ── Statistik och register ───────────────────────────────────────
    "LANDVEX_SCB_BASE": _v(
        "recommended", "Statistics Sweden PxWeb base URL.",
        "Population, income and density fall back to mock, labelled mock, "
        "and data_coverage drops accordingly.",
        example="https://api.scb.se/OV0104/v1/doris/en/ssd"),
    "LANDVEX_KOLADA_URL": _v(
        "recommended", "Kolada API base — municipal KPIs and livability.",
        "Care supply, school outcomes and crime index fall back to mock.",
        example="https://api.kolada.se/v2"),
    "LANDVEX_EUROSTAT_LIVE": _v(
        "optional", "Eurostat base URL for EU-wide livability signals.",
        "EU markets use mock for the signals Eurostat would provide."),
    "LANDVEX_EUROSTAT_DATASET": _v(
        "optional", "Override the Eurostat dataset id.",
        "The documented default dataset is used."),
    "LANDVEX_REGISTER_URL": _v(
        "optional", "Own mirror of a business register.",
        "National authority APIs are used instead; without those, "
        "saturation refuses rather than inventing a count."),
    "LANDVEX_SCB_ESTAB_TABLE": _v(
        "optional", "PxWeb table id for Swedish establishments.",
        "The documented table id is used."),
    "LANDVEX_SSB_BASE": _v("optional", "Statistics Norway PxWeb base.",
                           "The documented base is used."),
    "LANDVEX_SSB_ESTAB_TABLE": _v("optional", "SSB establishments table.",
                                  "The documented table id is used."),
    "LANDVEX_DST_BASE": _v("optional", "Statistics Denmark base.",
                           "The documented base is used."),
    "LANDVEX_DST_ESTAB_TABLE": _v("optional", "DST establishments table.",
                                  "The documented table id is used."),
    "LANDVEX_STATFIN_BASE": _v("optional", "Statistics Finland base.",
                               "The documented base is used."),
    "LANDVEX_STATFIN_ESTAB_TABLE": _v("optional", "StatFin table id.",
                                      "The documented table id is used."),
    "LANDVEX_CENSUS_BASE": _v("optional", "US Census CBP base URL.",
                              "The documented base is used."),
    "LANDVEX_CENSUS_YEAR": _v("optional", "CBP survey year.",
                              "The documented default year is used."),
    "LANDVEX_GEO_URL": _v(
        "optional", "Administrative boundary service.",
        "Region lookup uses the built-in table, which covers the markets "
        "listed in /v1/markets."),

    # ── Övriga datakällor ────────────────────────────────────────────
    "LANDVEX_PERMITS_URL": _v(
        "optional", "Building permits and detail plans feed.",
        "Permit signals are mock; the brief cannot check a structure "
        "change against a permit."),
    "LANDVEX_PLACES_URL": _v(
        "optional", "Places / competition source.",
        "Competition pressure and provider gap are mock."),
    "LANDVEX_PROGRAMS_URL": _v(
        "optional", "Support-programme feed.",
        "Programme matching is mock."),
    "LANDVEX_SVK_URL": _v(
        "optional", "Svenska kraftnät / ENTSO-E grid telemetry.",
        "Grid production mix and balance are mock."),

    # ── Sensorer (se /v1/sensors) ────────────────────────────────────
    "LANDVEX_TRAFFIC_URL": _v(
        "optional", "Trafikverket TrafficFlow endpoint.",
        "Road flow is not measured at all. traffic_shift then rests on "
        "one network instead of two.",
        example="https://api.trafikinfo.trafikverket.se/v2/data.json"),
    "LANDVEX_TRAFFIC_KEY": _v(
        "optional", "Trafikverket authentication key (free).",
        "No call is made even if the URL is set — there is no way in "
        "without it.", secret=True),
    "LANDVEX_TRAFFIC_FI_URL": _v(
        "optional", "Digitraffic road (Finland). No key required.",
        "The SECOND independent road network is missing, so road flow "
        "cannot be corroborated.",
        example="https://tie.digitraffic.fi"),
    "LANDVEX_WEATHER_URL": _v(
        "optional", "SMHI metobs base. No key required.",
        "Weather cannot be used to rule out a cause for an anomaly.",
        example="https://opendata-download-metobs.smhi.se"),
    "LANDVEX_WEATHER_US_URL": _v(
        "optional", "NOAA/NWS base. No key required.",
        "The second independent weather network is missing.",
        example="https://api.weather.gov"),
    "LANDVEX_WEATHER_STATION": _v(
        "optional", "Station id the weather probe checks.",
        "The probe uses a documented default station."),
    "LANDVEX_AIR_URL": _v("optional", "OpenAQ v3 base.",
                          "Air quality is not measured.",
                          example="https://api.openaq.org"),
    "LANDVEX_AIR_KEY": _v("optional", "OpenAQ API key (free).",
                          "No call is made even with the URL set.",
                          secret=True),
    "LANDVEX_HYDRO_URL": _v("optional", "SMHI hydrology base.",
                            "Water level and discharge are not measured."),
    "LANDVEX_HYDRO_STATION": _v("optional", "Station id for the hydro probe.",
                                "The probe uses a documented default."),
    "LANDVEX_EO_URL": _v(
        "optional", "Copernicus STAC search endpoint.",
        "Satellite coverage cannot be checked, so the platform cannot "
        "tell 'nothing changed' from 'nothing was observed'."),
    "LANDVEX_EO_FROM": _v("optional", "Start of the EO probe window.",
                          "The probe uses a documented default window."),
    "LANDVEX_EO_TO": _v("optional", "End of the EO probe window.",
                        "The probe uses a documented default window."),
    "LANDVEX_SEISMIC_URL": _v("optional", "USGS FDSN base. No key required.",
                              "Seismic events are not read.",
                              example="https://earthquake.usgs.gov"),
    "LANDVEX_AIS_URL": _v("optional", "Digitraffic marine AIS. No key.",
                          "Vessel movements are not read.",
                          example="https://meri.digitraffic.fi"),
    "LANDVEX_METER_URL": _v(
        "optional", "Owner-supplied sensor feed base "
                    "(building meters, district heating, water, waste).",
        "Every owner-supplied stream is unavailable."),
    "LANDVEX_METER_STREAM": _v("optional", "Stream id the meter probe reads.",
                               "The meter probe reports 'not configured'."),

    # ── Tabell-id:n som bara behöver röras om en myndighet flyttar ──
    "LANDVEX_SCB_POP_TABLE": _v("optional", "PxWeb table for population.",
                                "The documented table id is used."),
    "LANDVEX_SCB_INCOME_TABLE": _v("optional", "PxWeb table for income.",
                                   "The documented table id is used."),
    "LANDVEX_SCB_DENSITY_TABLE": _v("optional", "PxWeb table for density.",
                                    "The documented table id is used."),
    "LANDVEX_EUROSTAT_BASE": _v("optional", "Eurostat API base URL.",
                                "The documented base is used."),
    "LANDVEX_CENSUS_KEY": _v(
        "optional", "US Census API key. Optional even upstream — Census "
                    "allows anonymous calls at a lower rate.",
        "Calls go unauthenticated and are rate-limited harder.",
        secret=True),

    # ── Hur många skrivare ───────────────────────────────────────────
    # Behövs för att kunna skilja ett legitimt SQLite-bygge från ett som
    # tappar data. En varning som aldrig går att bli av med lärs man sig
    # att klicka förbi.
    "WEB_CONCURRENCY": _v(
        "recommended", "Gunicorn worker processes in one container.",
        "The image defaults to 2. Two workers on one SQLite file is two "
        "writers on one file — set it to 1, or move to PostgreSQL.",
        example="2"),
    "LANDVEX_REPLICAS": _v(
        "optional", "How many tasks will run behind the load balancer. "
                    "Read only by preflight, to judge the storage choice.",
        "Preflight falls back to WEB_CONCURRENCY, and to 2 if neither is "
        "set — because that is what the shipped image runs.",
        example="3"),
    "LANDVEX_PREFLIGHT": _v(
        "recommended", "What a failed preflight costs at container start: "
                       "'strict' refuses to serve, 'warn' logs and serves, "
                       "'off' skips the check.",
        "Defaults to 'warn': the container starts and the reasons are in "
        "the first lines of the log. Set 'strict' in production so a "
        "misconfigured task never reaches the load balancer.",
        example="strict"),

    # ── Verktyg ──────────────────────────────────────────────────────
    "LANDVEX_API_KEY": _v(
        "optional", "Single key used BY scripts/readiness_check.py to call "
                    "a running server. Not read by the server itself — "
                    "that one is LANDVEX_API_KEYS, plural.",
        "The readiness check calls unauthenticated, which only works "
        "against a server running in open mode.",
        secret=True),

    # ── quiXzoom och AAMOS ───────────────────────────────────────────
    "LANDVEX_QUIXZOOM_URL": _v(
        "optional", "Direct quiXzoom observations endpoint.",
        "Field observations come through AAMOS if that is configured, "
        "otherwise not at all."),
    "LANDVEX_QUIXZOOM_KEY": _v("optional", "quiXzoom API key.",
                               "Requests go unauthenticated and will "
                               "likely be refused.", secret=True),
    "LANDVEX_QUIXZOOM_PATH": _v("optional", "Observations path override.",
                                "The documented path is used."),
    "LANDVEX_QUIXZOOM_MISSION_PATH": _v(
        "optional", "Path quiXzoom accepts a mission ORDER on. Reading "
                    "missions and ordering one are different endpoints.",
        "The documented default path is used. Ordering still refuses "
        "entirely unless LANDVEX_QUIXZOOM_URL is set — no mission id is "
        "ever invented.",
        example="/api/missions"),
    "LANDVEX_SCHEDULER": _v(
        "optional", "Turn on the in-process ticker that runs due scheduled "
                    "jobs (POST /v1/schedules/run does the same work).",
        "Off. Nothing runs unattended: a background thread that starts "
        "because a module was imported, and then orders field missions "
        "for a customer, is an expensive surprise. Point EventBridge or "
        "cron at the endpoint instead when running more than one "
        "instance.",
        example="on"),
    "LANDVEX_SCHEDULER_INTERVAL_S": _v(
        "optional", "Seconds between ticks when the scheduler is on.",
        "60 seconds. Values below 5 are raised to 5 — the cadence lives "
        "in the job, not in the tick.",
        example="60"),
    "LANDVEX_QUIXZOOM_AUTH_HEADER": _v(
        "optional", "Header name for the quiXzoom key.",
        "The documented default header is used."),
    "AAMOS_CORE_URL": _v(
        "optional", "AAMOS Capability Platform base URL.",
        "Platform status, agents and cognition report not-connected "
        "honestly, and service self-registration is skipped."),
    "AAMOS_TOKEN": _v(
        "optional", "AAMOS bearer token — a service-account token issued "
                    "by AAMOS admin. Never mint or forge one: a token this "
                    "side signs itself proves nothing about who is calling.",
        "Requests go unauthenticated, and AAMOS-backed endpoints report "
        "not-connected honestly rather than failing.", secret=True),
    "AAMOS_API_KEY": _v("optional", "AAMOS API key.",
                        "Requests go unauthenticated.", secret=True),
    "AAMOS_AUTH_HEADER": _v("optional", "Custom AAMOS auth header name.",
                            "Standard Authorization / X-API-Key are used."),
    "AAMOS_AUTH_VALUE": _v("optional", "Value for that custom header.",
                           "No custom header is sent.", secret=True),
    "AAMOS_TIMEOUT": _v("optional", "AAMOS request timeout in seconds.",
                        "The documented default timeout is used."),
    "AAMOS_QUIXZOOM_PATH": _v("optional", "quiXzoom path inside AAMOS.",
                              "The documented path is used."),
}


# Variabler som applikationen ALDRIG läser, men som det som startar den
# gör. De hör inte hemma i preflight — processen kan inte se dem och kan
# inte uttala sig om dem — men de måste stå i miljömallen, annars tappas
# de tyst när mallen genereras. Ett test håller listan mot
# docker-compose.yml åt båda håll.
ORCHESTRATION: dict[str, dict] = {
    "APP_BIND": _v(
        "recommended", "host:port docker-compose publishes the app on.",
        "Defaults to 127.0.0.1:8000 — reachable from the host, not from "
        "the network. Change it deliberately, not by accident.",
        example="127.0.0.1:8000"),
    "PGUSER": _v("optional", "User for the compose-managed PostgreSQL.",
                 "Defaults to 'landvex'.", example="landvex"),
    "PGPASSWORD": _v(
        "optional", "Password for the compose-managed PostgreSQL.",
        "Defaults to 'changeme', which is fine on a laptop and nowhere "
        "else. In AWS this database does not exist — Aurora does, and "
        "its DSN lives in Secrets Manager.", secret=True),
    "PGDATABASE": _v("optional", "Database name for the compose profile.",
                     "Defaults to 'landvex'.", example="landvex"),
}


def redact(name: str, value: str) -> str:
    """Ett hemligt värde får aldrig lämna processen i klartext."""
    if not value:
        return ""
    if ENVIRONMENT.get(name, {}).get("secret") or \
            ORCHESTRATION.get(name, {}).get("secret"):
        return f"set ({len(value)} chars)"
    return value


def by_tier(tier: str) -> list[str]:
    return sorted(k for k, v in ENVIRONMENT.items() if v["tier"] == tier)


def writers(env: dict) -> int:
    """Hur många processer som samtidigt kan skriva till lagret.

    Uppgifter GÅNGER arbetare per uppgift — tre uppgifter med en arbetare
    var är lika många skrivare som en uppgift med tre. Arbetare utan
    angivelse räknas som 2, för det är vad imagen faktiskt startar; att
    gissa 1 hade gjort standardfallet grönt utan att det är sant.
    """
    def _tal(namn: str, standard: int) -> int:
        try:
            n = int(str(env.get(namn, "")).strip())
        except ValueError:
            return standard
        return n if n > 0 else standard

    return _tal("LANDVEX_REPLICAS", 1) * _tal("WEB_CONCURRENCY", 2)


def preflight(env: dict | None = None) -> dict:
    """Är den här miljön redo? Rapporterar, avgör inte.

    Returnerar `blocking` (systemet startar osäkert eller tappar data) och
    `degraded` (fungerar, men sämre eller mindre ärligt). Anroparen —
    scripts/preflight.py — bestämmer vad det ska kosta.
    """
    env = os.environ if env is None else env
    satta, blockerande, forsamrat = [], [], []

    for namn, v in sorted(ENVIRONMENT.items()):
        varde = env.get(namn, "")
        if varde:
            satta.append({"name": namn, "value": redact(namn, varde),
                          "tier": v["tier"]})
            continue
        rad = {"name": namn, "consequence_en": v["if_unset_en"],
               "purpose_en": v["purpose_en"], "example": v["example"]}
        if v["tier"] == "required":
            blockerande.append(rad)
        elif v["tier"] == "recommended":
            forsamrat.append(rad)

    # Två kombinationer som är farligare än summan av delarna.
    varningar = []
    if not env.get("LANDVEX_API_KEYS") and not env.get("LANDVEX_JWT_SECRET"):
        varningar.append({
            "issue_en": "The API is running OPEN.",
            "detail_en": "With neither LANDVEX_API_KEYS nor "
                         "LANDVEX_JWT_SECRET set, every caller is an admin "
                         "of tenant 'dev' on the enterprise plan. Tenant "
                         "isolation is enforced per tenant — and everyone "
                         "is the same tenant."})
    db = env.get("LANDVEX_DB", "")
    n_skrivare = writers(env)
    pa_sqlite = not env.get("LANDVEX_PG_DSN") and db.lower() not in ("off", "0")
    if pa_sqlite and n_skrivare > 1:
        varningar.append({
            "issue_en": f"SQLite with {n_skrivare} writers loses data.",
            "detail_en": f"One file, one writer — and this environment "
                         f"starts {n_skrivare} of them (LANDVEX_REPLICAS × "
                         f"WEB_CONCURRENCY). Two tasks behind a load "
                         f"balancer will not share the file, and quota "
                         f"counting and the decision ledger diverge "
                         f"silently. Set LANDVEX_PG_DSN, or WEB_CONCURRENCY"
                         f"=1 on a single task, or LANDVEX_DB=off to be "
                         f"stateless on purpose."})
    elif pa_sqlite:
        # Ett medvetet enprocessbygge med monterad volym är ett giltigt
        # val, inte ett fel. Att varna ändå hade lärt läsaren att klicka
        # förbi varningarna — och då fyller de ingen funktion när det
        # gäller. Det står kvar som en FÖRSÄMRING, med taket utskrivet.
        for rad in forsamrat:
            if rad["name"] == "LANDVEX_PG_DSN":
                rad["consequence_en"] = (
                    "Running on SQLite with a single writer. Valid with a "
                    "mounted volume, and it caps the deployment at one "
                    "task: scaling out requires PostgreSQL first.")

    return {
        "set": satta, "blocking": blockerande, "degraded": forsamrat,
        "warnings": varningar,
        "ready": not blockerande and not varningar,
        "counts": {"set": len(satta), "blocking": len(blockerande),
                   "degraded": len(forsamrat), "warnings": len(varningar)},
        "note_en": ("Unset is not the same as broken: most of these are "
                    "sources the platform degrades away from honestly. "
                    "What matters is that the degradation is CHOSEN rather "
                    "than discovered after launch."),
    }
