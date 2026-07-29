"""Licens- och paketlagret – plattformsnivåer, produkter och priser.

Tre plannivåer (Free/Growth/Enterprise; plan-id:t för Growth är fort-
farande "pro" – nyckelformatet är ett kontrakt, PLAN_ALIASES mappar
"growth" → "pro") + produktmoduler som kan köpas
separat som tillägg. Allt är data: nytt paket eller prisändring = ny
rad, ingen kodändring. Priserna är LISTPRISER (prisexempel) och
konfigureras per avtal/marknad i produktionsfasen – de är medvetet
inte hårdkodade sanningar.

Enforcement sker i api/security.py:
  - API-nyckelformat: nyckel:tenant:roll[:plan[:tillägg|tillägg]]
    (bakåtkompatibelt: utan plan ⇒ enterprise, för befintliga miljöer)
  - Varje endpoint kräver en kapabilitet; plan + tillägg ger
    kapabiliteter (resolve_capabilities).
  - Rate limit per plan (Free 60/min, Pro 600, Enterprise 3000).
  - Live-indexlager (Intelligence Map) kräver intelligence_map_live –
    "free historical data / live requires subscription".
"""
from __future__ import annotations

from engine.commission import commission_catalog

# ── Kapabiliteter per endpoint (prefixmatch, längsta vinner) ─────────
ENDPOINT_CAPABILITY: dict[str, str] = {
    "/v1/ask": "core",
    "/v1/markets": "core",
    "/v1/catalog": "core",
    "/v1/profile-options": "core",
    "/v1/segments": "core",           # katalogen; analysen kräver opportunity
    "/v1/segments/analyze": "opportunity",
    "/v1/segments/map": "opportunity",
    "/v1/analyze": "opportunity",
    "/v1/scan": "opportunity",
    "/v1/profiles": "opportunity",
    "/v1/compare": "opportunity",
    "/v1/risk": "opportunity",
    "/v1/gaps": "opportunity",
    "/v1/plan": "opportunity",
    "/v1/opportunities": "opportunity",
    "/v1/risk-intelligence": "opportunity",
    "/v1/reports": "opportunity",
    "/v1/workforce": "workforce",
    "/v1/products": "demand_intelligence",
    "/v1/service": "demand_intelligence",
    "/v1/indices": "intelligence_map_free",   # live-lager kräver _live
    "/v1/kpi": "core",                        # registret; evaluate kräver mer
    "/v1/kpi/evaluate": "opportunity",
    "/v1/lambda": "opportunity",
    "/v1/setpoints": "core",                  # registret; assess kräver mer
    "/v1/setpoints/assess": "opportunity",
    "/v1/cite": "core",                       # citat/proveniens öppet
    "/v1/feeds": "core",                      # feed-katalog; events kräver mer
    "/v1/feeds/events": "opportunity",
    "/v1/worthiness": "opportunity",
    "/v1/decision": "opportunity",
    "/v1/strim": "core",                      # kunskapsgraf + status öppna
    "/v1/kolada": "core",
    "/v1/svk": "core",
    "/v1/outcomes": "opportunity",            # utfallslogg + kalibrering + roi
    "/v1/decisions": "opportunity",           # ansvarsloop (commit/resolve/ledger)
    "/v1/correlate": "opportunity",           # tvärdomän-korrelation
    "/v1/scenario": "opportunity",            # trovärdighets-grindade scenarier
    "/v1/event-study": "opportunity",         # före/efter + diff-in-diff
    "/v1/benchmark": "opportunity",           # peer-benchmark
    "/v1/sensitive-association": "opportunity",  # känsliga kategorier (grindad)
    "/v1/wages": "core",                      # löneregister (katalog); analys mer
    "/v1/wages/lookup": "opportunity",
    "/v1/wages/compare": "opportunity",
    "/v1/corrections": "core",                # wiki-rättelser (medborgarbidrag)
    "/v1/sources": "core",                    # anslutnings-cockpit (live/mock)
    "/v1/entrypoints": "core",                # roll-baserade ingångar (overlay)
    "/v1/admin": "core",                      # administrativt register
    "/v1/monitors": "monitoring",             # bevakningar + cron (styrd API)
    # Schemaläggning är ingen egen produkt — det är en egenskap hos det
    # kunden redan köpt. Vägen är därför öppen och JOBBTYPEN grindas:
    # ett schemalagt svep kräver opportunity, en schemalagd
    # uppdragsbeställning asset_inspections, en väckt bevakning
    # monitoring. Låg hela vägen på "monitoring" kunde flaggleverantören
    # — vars hela behov är "beställ kontrollerna varje vecka utan att
    # jag ber om det" — inte schemalägga det hon köpt.
    "/v1/schedules": "core",
    "/v1/inbox": "monitoring",                # händelseroutning per intresse
    # Katalogen (GET) måste vara läsbar utan att först ha köpt något —
    # samma skäl som /v1/offering. Skyddet ligger i stället på
    # DATAMÄNGDEN: POST /v1/export kräver samma kapabilitet som den
    # endpoint datamängden kommer ifrån, annars vore exporten en väg runt
    # paketet (köp export, läs allt).
    # Täckningsytan är publik med flit: den som måste köpa för att
    # få veta vad talen vilar på har redan fått fel produkt.
    # Sökningen är analys, inte katalog — samma paket som svepet.
    "/v1/analysis": "opportunity",
    # Ett index som bara betalande kan öppna är ett omdöme
    # med en siffra på. Samma grund som /v1/coverage.
    "/v1/mrai": "core",
    # Sponsorportalen: annonsörens egen yta. Egen kapabilitet, för det
    # är en annan KUND än den som köper beslutsstöd — och statistiken
    # är k-golvad oavsett paket.
    # Infrastrukturövervakningen säljs till parkeringsoperatörer,
    # kommuner och fastighetsägare — samma kundtyp som kontrollerna,
    # samma paket.
    "/v1/infrastructure": "asset_inspections",
    "/v1/land": "opportunity",                # markvärdesläget hör till
                                              # etableringsbeslutet — samma
                                              # paket som /v1/plan och
                                              # /v1/saturation
    "/v1/sponsorship": "sponsor_portal",
    "/v1/connections": "core",                # kundens eget kryp-in: egna
                                              # nycklar och webhooks — följer
                                              # kontot, inte något tilläggspaket
    "/v1/company": "core",                    # varumärket som rider på uppdragen
    "/v1/credentials": "core",                # kvittona och verifieringen
    "/v1/staff": "asset_inspections",         # egna zoomers riktar fotouppdrag
                                              # — samma paket som kontrollerna
    "/v1/deliveries": "core",                 # utgångens revisionslogg
    "/v1/pushes": "core",                     # generatorns valrymd + preview
                                              # — datamängdens EGEN
                                              # kapabilitet prövas därtill
                                              # i handlern, som för export
    "/v1/integrity": "core",                  # självrevisionen — den som
                                              # ska lita på plattformen får
                                              # se granskningen utan att
                                              # köpa något; /v1/audit
                                              # (säkerhetsloggen) är en
                                              # annan yta och förblir
                                              # platform_ops

    "/v1/coverage": "core",
    "/v1/export": "core",
    "/v1/assets": "asset_inspections",        # kundens egna objekt
    "/v1/routines": "asset_inspections",      # hur ofta de ska kontrolleras
    "/v1/inspections": "asset_inspections",   # förfall, beställning, dom,
                                              # efterlevnad, avvikelser
    "/v1/visitor": "core",                    # onboarding-sömmen
    "/v1/customer": "core",                   # kundresan KYC→aktiv
    "/v1/flows": "opportunity",               # kostnad/nytta (förväntat värde)
    "/v1/saturation": "opportunity",          # marknadsmättnad per bransch
    "/v1/merit": "opportunity",               # mätbar prestation (merit)
    "/v1/livability": "opportunity",          # hushållsviktade livsvillkor
    "/v1/households": "core",                 # hushållstyper (katalog)
    "/v1/registers": "core",                  # företagsregisterkartan
    "/v1/provenance": "core",                 # parametrarnas härkomst
    "/v1/corroboration": "core",              # hur väl underbyggt något är
    "/v1/sensors": "core",                    # vad som kan mätas, och inte
    "/v1/surface": "core",                    # de fyra löftena — ytan
    "/v1/chain": "core",                      # de fyra avsikterna + kedjorna
    "/v1/offering": "core",                   # vad varje nivå låter dig BESLUTA
                                              # — måste vara läsbar utan att
                                              # först ha köpt något
    "/v1/brief": "monitoring",                # proaktiv upptäckt (daily brief)
    # De tre raderna nedan fanns inte, och det syntes inte: en väg utan
    # rad kräver giltig nyckel men släpper in VARJE plan. "Ogatad" ser
    # exakt likadan ut som "medvetet öppen" tills någon läser hela ytan
    # — vilket tests/test_licensing numera gör.
    "/v1/verticals": "core",                  # katalog, som syskonen
                                              # /v1/markets, /v1/segments
    "/v1/commercial": "core",                 # säljytan — samma grund som
                                              # /v1/offering: läsbar utan köp
    "/v1/entitlements": "core",               # anroparens EGNA rättigheter;
                                              # core bärs av varje plan, så
                                              # ingen betalande kan 403:as
    "/v1/agent-manifest": "partner_api",
    "/v1/audit": "platform_ops",
    "/metrics": "platform_ops",
    "/v1/report": "opportunity",
    "/v1/platform/status": "core",
    "/v1/watch": "platform_ops",
    "/v1/agents": "partner_api",
    "/v1/cognition": "partner_api",
}

# Plannamn enligt AAMOS-konventionen: "growth" är alias för plan-id:t
# "pro" (id:t är ett kontrakt i nyckelformatet och ändras inte).
# Ytnamn → plan-id. Id:t sitter i nyckelformatet och ändras aldrig;
# "growth" behålls eftersom befintliga nycklar använder det.
PLAN_ALIASES: dict[str, str] = {"growth": "pro", "professional": "pro",
                                "explorer": "free",
                                "enterprise intelligence": "enterprise"}


class _PlanMap(dict):
    """dict som slår upp via PLAN_ALIASES men itererar kanoniska id:n.

    Gör att nycklar skrivna `key:tenant:role:growth` fungerar överallt
    där planer valideras eller slås upp (t.ex. rate limit per plan i
    api/security.py) – utan att kataloger/tester ser dubbletter.
    """

    def __getitem__(self, key):
        return super().__getitem__(PLAN_ALIASES.get(key, key))

    def get(self, key, default=None):
        return super().get(PLAN_ALIASES.get(key, key), default)

    def __contains__(self, key):
        return super().__contains__(PLAN_ALIASES.get(key, key))


PLANS: dict[str, dict] = _PlanMap({
    "free": {
        "label_en": "Landvex Explorer",
        "beskrivning_en": "Settle whether a claim about a place holds up, on "
                          "public findings. For exploring what the platform "
                          "can decide — not for commercial use.",
        "pris_manad": {"USD": 0, "EUR": 0},
        "rate_limit_per_min": 60,
        "quota_per_month": 100,
        "capabilities": ("core", "intelligence_map_free"),
        "ingar_en": ["Ask Landvex (/v1/ask)",
                     "Free Intelligence Map layers (historical)",
                     "Market and product catalogs"],
    },
    "pro": {
        "label_en": "Landvex Professional",
        "beskrivning_en": "Decide where to establish, whether a market has room, "
                          "what a place will be short of, and whether a "
                          "spend is worth it — in your region and trade. "
                          "Billed as quiXzoom commission per delivered lead, "
                          "no monthly fee.",
        # Bekräftat av AAMOS-dev: Growth har INGEN månadsavgift. Priset är
        # en per-lead-kommission (QZ TOKEN), graderad av opportunity-score.
        # Se engine/commission.py för nivåtabellen.
        "pris_manad": None,
        "kommission": commission_catalog(),
        "rate_limit_per_min": 600,
        "quota_per_month": 10000,
        "capabilities": ("core", "opportunity", "workforce",
                         "demand_intelligence", "intelligence_map_free",
                         "intelligence_map_live", "monitoring"),
        "ingar_en": ["Everything in Free",
                     "Opportunity: market sweeps, gap analysis, "
                     "establishment plans, risk, comparisons, segments",
                     "Workforce: forecasts, simulation, shortage maps",
                     "Demand Intelligence: installed base & service needs",
                     "Control Monitors: scheduled watches (cron), anomaly "
                     "detection, escalation to owned decisions",
                     "Intelligence Map incl. live layers",
                     "AAMOS platform status & integrations (live once "
                     "AAMOS_CORE_URL is set)",
                     "Billing: quiXzoom commission 0.05–0.15 QZ per "
                     "lead (by opportunity score) – no monthly fee"],
    },
    "enterprise": {
        "label_en": "Landvex Enterprise Intelligence",
        "beskrivning_en": "A standing intelligence capability: detection without "
                          "being asked, your own watch rules, decisions bound "
                          "to named owners, and machine access for your own "
                          "systems.",
        "pris_manad": None,          # offert
        "rate_limit_per_min": 3000,
        "quota_per_month": None,   # obegränsat
        "capabilities": ("core", "opportunity", "workforce",
                         "demand_intelligence", "intelligence_map_free",
                         "intelligence_map_live", "monitoring", "partner_api",
                         "platform_ops", "asset_inspections",
                         "sponsor_portal"),
        "ingar_en": ["Everything in Professional",
                     "Asset inspections: your own objects, recurring "
                     "routines, field orders, verdicts and a compliance "
                     "record (also sold as an add-on to any plan — a "
                     "contractor with 300 flagpoles is not an enterprise)",
                     "Partner API + agent manifest",
                     "AAMOS agents, watchlist and cognition endpoints "
                     "(requires AAMOS_CORE_URL)",
                     "Metrics and audit visibility via API",
                     "OIDC/SSO and tenant isolation (AWS phase)",
                     "SLA and dedicated support"],
    },
})

# Produktmoduler som tillägg (t.ex. Free + enbart Workforce).
ADDONS: dict[str, dict] = {
    "opportunity": {"label_en": "Opportunity Engine",
                    "pris_manad": {"USD": 149, "EUR": 139},
                    "capabilities": ("opportunity",)},
    "workforce": {"label_en": "Workforce Intelligence",
                  "pris_manad": {"USD": 199, "EUR": 185},
                  "capabilities": ("workforce",)},
    "demand_intelligence": {"label_en": "Demand Intelligence",
                            "pris_manad": {"USD": 199, "EUR": 185},
                            "capabilities": ("demand_intelligence",)},
    "intelligence_map": {"label_en": "Intelligence Map Live",
                         "pris_manad": {"USD": 149, "EUR": 139},
                         "capabilities": ("intelligence_map_live",)},
    # Tillägget finns för att den första riktiga kunden för modulen — en
    # flaggleverantör som sköter flaggor och flaggstänger i stora delar av
    # Stockholm — inte är ett enterpriseföretag. Ligger kapabiliteten bara
    # i den dyraste planen kan hon inte köpa det hon behöver.
    "asset_inspections": {"label_en": "Asset Inspections",
                          "pris_manad": {"USD": 249, "EUR": 229},
                          "capabilities": ("asset_inspections",)},
    "partner_api": {"label_en": "Partner API & Agents",
                    "pris_manad": {"USD": 499, "EUR": 459},
                    "capabilities": ("partner_api",)},
    # Sponsorportalen köps av annonsören, inte av den som köper
    # beslutsstöd — därför ett eget tillägg och inte en planrad. Vad
    # sponsorn får se är k-golvat oavsett vad hen betalar: paketet
    # styr åtkomst, aldrig upplösning.
    "sponsor_portal": {"label_en": "Sponsor Portal (sponsored missions)",
                       "pris_manad": {"USD": 399, "EUR": 369},
                       "capabilities": ("sponsor_portal",)},
}

PRISNOT_EN = ("List prices (examples) in USD per month excl. taxes – "
              "configured per contract, market and volume.")


def resolve_capabilities(plan: str, addons: tuple[str, ...] = ()) -> frozenset:
    plan = PLAN_ALIASES.get(plan, plan)
    if plan not in PLANS:
        raise ValueError(f"Unknown plan: {plan}. "
                         f"Available: {', '.join(PLANS)}")
    caps = set(PLANS[plan]["capabilities"])
    for a in addons:
        if a not in ADDONS:
            raise ValueError(f"Unknown add-on: {a}. "
                             f"Available: {', '.join(ADDONS)}")
        caps.update(ADDONS[a]["capabilities"])
    return frozenset(caps)


def required_capability(path: str) -> str | None:
    base = path.split("?")[0].rstrip("/")
    best = None
    for prefix, cap in ENDPOINT_CAPABILITY.items():
        if base == prefix or base.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, cap)
    return best[1] if best else None


def upgrade_hint_en(capability: str) -> str:
    """Vilka paket låser upp kapabiliteten – för 403-svaret."""
    plans = [p["label_en"] for p in PLANS.values()
             if capability in p["capabilities"]]
    addons = [a["label_en"] for a in ADDONS.values()
              if capability in a["capabilities"]]
    delar = plans + [f"the {a} add-on" for a in addons]
    return (f"Requires {' or '.join(delar)} – see /v1/plans."
            if delar else "This capability is not part of any package yet.")


def plans_catalog() -> dict:
    return {"plans": [{"id": pid, **{k: v for k, v in p.items()
                                     if k != "capabilities"},
                       "capabilities": list(p["capabilities"])}
                      for pid, p in PLANS.items()],
            "tillagg": [{"id": aid, **{k: v for k, v in a.items()
                                       if k != "capabilities"},
                         "capabilities": list(a["capabilities"])}
                        for aid, a in ADDONS.items()],
            "prisnot_en": PRISNOT_EN}


# --- Query-complexity-budget + månadsfönster (dissg monetarisering) ---------
# Per-plan komplexitetstak (0 = obegränsat). En tung fråga (många dimensioner,
# djup historik) kostar mer; budgeten skiljer plus/pro/enterprise.
COMPLEXITY_LIMIT: dict[str, int] = {"free": 100, "pro": 1000, "enterprise": 0}


def complexity_limit(plan: str) -> int:
    return COMPLEXITY_LIMIT.get(PLAN_ALIASES.get(plan, plan), 100)


def check_complexity(plan: str, cost: int) -> bool:
    """True om en fråga med kostnad `cost` ryms i planens budget."""
    lim = complexity_limit(plan)
    return lim == 0 or int(cost) <= lim


def usage_window_key(tenant: str, feature: str, year_month: str) -> str:
    """Nyckel för månadsvis kvoträkning: (tenant, feature, 'YYYY-MM').

    year_month skickas in (aldrig härlett i lagret) → deterministiskt och
    testbart, och överlever omstarter i det persistenta usage_meter-lagret.
    """
    return f"{tenant}:{feature}:{year_month}"
