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
    "/v1/reports": "opportunity",
    "/v1/workforce": "workforce",
    "/v1/products": "demand_intelligence",
    "/v1/service": "demand_intelligence",
    "/v1/indices": "intelligence_map_free",   # live-lager kräver _live
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
        "beskrivning_en": "All decision engines and live map layers for "
                          "one organization.",
        "pris_manad": {"USD": 499, "EUR": 459},
        # Kommissionsmodell (beslut från AAMOS-dev): 0.15 QZ TOKEN per
        # levererad lead. ÖPPEN FRÅGA: ersätter detta månadsavgiften
        # eller är det ett tillägg? Gäller det plattformsbrett? Fältet är
        # data tills det bekräftas – enforcement använder ännu quota.
        "kommission": {"qz_token_per_lead": 0.15, "modell": "commission"},
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
                     "AAMOS_CORE_URL is set)"],
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
