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
PLAN_ALIASES: dict[str, str] = {"growth": "pro"}


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
        "label_en": "Landvex Free",
        "beskrivning_en": "Ask the platform and view the free map layers. "
                          "Historical base – live requires a subscription.",
        "pris_manad": {"USD": 0, "EUR": 0},
        "rate_limit_per_min": 60,
        "quota_per_month": 100,
        "capabilities": ("core", "intelligence_map_free"),
        "ingar_en": ["Ask Landvex (/v1/ask)",
                     "Free Intelligence Map layers (historical)",
                     "Market and product catalogs"],
    },
    "pro": {
        "label_en": "Landvex Growth",
        "beskrivning_en": "All decision engines and live map layers, "
                          "billed as quiXzoom commission per delivered "
                          "lead – no monthly fee.",
        # Bekräftat av AAMOS-dev: Growth har INGEN månadsavgift. Priset är
        # en per-lead-kommission (QZ TOKEN), graderad av opportunity-score.
        # Se engine/commission.py för nivåtabellen.
        "pris_manad": None,
        "kommission": commission_catalog(),
        "rate_limit_per_min": 600,
        "quota_per_month": 10000,
        "capabilities": ("core", "opportunity", "workforce",
                         "demand_intelligence", "intelligence_map_free",
                         "intelligence_map_live"),
        "ingar_en": ["Everything in Free",
                     "Opportunity: market sweeps, gap analysis, "
                     "establishment plans, risk, comparisons, segments",
                     "Workforce: forecasts, simulation, shortage maps",
                     "Demand Intelligence: installed base & service needs",
                     "Intelligence Map incl. live layers",
                     "AAMOS platform status & integrations (live once "
                     "AAMOS_CORE_URL is set)",
                     "Billing: quiXzoom commission 0.05–0.15 QZ per "
                     "lead (by opportunity score) – no monthly fee"],
    },
    "enterprise": {
        "label_en": "Landvex Enterprise",
        "beskrivning_en": "Partner API, agent integration, operations/"
                          "audit visibility, tenant isolation and SLA.",
        "pris_manad": None,          # offert
        "rate_limit_per_min": 3000,
        "quota_per_month": None,   # obegränsat
        "capabilities": ("core", "opportunity", "workforce",
                         "demand_intelligence", "intelligence_map_free",
                         "intelligence_map_live", "partner_api",
                         "platform_ops"),
        "ingar_en": ["Everything in Growth",
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
    "partner_api": {"label_en": "Partner API & Agents",
                    "pris_manad": {"USD": 499, "EUR": 459},
                    "capabilities": ("partner_api",)},
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
