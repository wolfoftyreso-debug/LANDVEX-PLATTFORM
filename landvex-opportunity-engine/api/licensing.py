"""Licens- och paketlagret – plattformsnivåer, produkter och priser.

Tre plannivåer (Free/Pro/Enterprise) + produktmoduler som kan köpas
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
}

PLANS: dict[str, dict] = {
    "free": {
        "label_sv": "Landvex Free",
        "beskrivning_sv": "Fråga plattformen och se de fria kartlagren. "
                          "Historisk bas – live kräver prenumeration.",
        "pris_manad": {"SEK": 0, "EUR": 0, "USD": 0},
        "rate_limit_per_min": 60,
        "capabilities": ("core", "intelligence_map_free"),
        "ingar_sv": ["Fråga Landvex (/v1/ask)",
                     "Fria Intelligence Map-lager (historik)",
                     "Marknads- och produktkataloger"],
    },
    "pro": {
        "label_sv": "Landvex Pro",
        "beskrivning_sv": "Alla beslutsmotorer och live-kartlager för "
                          "en organisation.",
        "pris_manad": {"SEK": 4900, "EUR": 450, "USD": 490},
        "rate_limit_per_min": 600,
        "capabilities": ("core", "opportunity", "workforce",
                         "demand_intelligence", "intelligence_map_free",
                         "intelligence_map_live"),
        "ingar_sv": ["Allt i Free",
                     "Opportunity: svep, gap-analys, etableringsplaner, "
                     "risk, jämförelser, målgrupper",
                     "Workforce: prognoser, simulering, bristkartor",
                     "Demand Intelligence: installerad bas & servicebehov",
                     "Intelligence Map inkl. live-lager"],
    },
    "enterprise": {
        "label_sv": "Landvex Enterprise",
        "beskrivning_sv": "Partner-API, agentintegration, drift-/"
                          "revisionsinsyn, tenant-isolering och SLA.",
        "pris_manad": None,          # offert
        "rate_limit_per_min": 3000,
        "capabilities": ("core", "opportunity", "workforce",
                         "demand_intelligence", "intelligence_map_free",
                         "intelligence_map_live", "partner_api",
                         "platform_ops"),
        "ingar_sv": ["Allt i Pro",
                     "Partner-API + agent-manifest",
                     "Metrics- och revisionsinsyn via API",
                     "OIDC/SSO och tenant-isolering (AWS-fasen)",
                     "SLA och dedikerad support"],
    },
}

# Produktmoduler som tillägg (t.ex. Free + enbart Workforce).
ADDONS: dict[str, dict] = {
    "opportunity": {"label_sv": "Opportunity Engine",
                    "pris_manad": {"SEK": 1490, "EUR": 135, "USD": 149},
                    "capabilities": ("opportunity",)},
    "workforce": {"label_sv": "Workforce Intelligence",
                  "pris_manad": {"SEK": 1990, "EUR": 180, "USD": 199},
                  "capabilities": ("workforce",)},
    "demand_intelligence": {"label_sv": "Demand Intelligence",
                            "pris_manad": {"SEK": 1990, "EUR": 180, "USD": 199},
                            "capabilities": ("demand_intelligence",)},
    "intelligence_map": {"label_sv": "Intelligence Map Live",
                         "pris_manad": {"SEK": 1490, "EUR": 135, "USD": 149},
                         "capabilities": ("intelligence_map_live",)},
    "partner_api": {"label_sv": "Partner-API & agenter",
                    "pris_manad": {"SEK": 4900, "EUR": 450, "USD": 490},
                    "capabilities": ("partner_api",)},
}

PRISNOT_SV = ("Listpriser (prisexempel) per månad exkl. moms – "
              "konfigureras per avtal, marknad och volym.")


def resolve_capabilities(plan: str, addons: tuple[str, ...] = ()) -> frozenset:
    if plan not in PLANS:
        raise ValueError(f"Okänd plan: {plan}. "
                         f"Tillgängliga: {', '.join(PLANS)}")
    caps = set(PLANS[plan]["capabilities"])
    for a in addons:
        if a not in ADDONS:
            raise ValueError(f"Okänt tillägg: {a}. "
                             f"Tillgängliga: {', '.join(ADDONS)}")
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


def upgrade_hint_sv(capability: str) -> str:
    """Vilka paket låser upp kapabiliteten – för 403-svaret."""
    plans = [p["label_sv"] for p in PLANS.values()
             if capability in p["capabilities"]]
    addons = [a["label_sv"] for a in ADDONS.values()
              if capability in a["capabilities"]]
    delar = plans + [f"tillägget {a}" for a in addons]
    return (f"Kräver {' eller '.join(delar)} – se /v1/plans."
            if delar else "Kapabiliteten ingår inte i något paket ännu.")


def plans_catalog() -> dict:
    return {"plans": [{"id": pid, **{k: v for k, v in p.items()
                                     if k != "capabilities"},
                       "capabilities": list(p["capabilities"])}
                      for pid, p in PLANS.items()],
            "tillagg": [{"id": aid, **{k: v for k, v in a.items()
                                       if k != "capabilities"},
                         "capabilities": list(a["capabilities"])}
                        for aid, a in ADDONS.items()],
            "prisnot_sv": PRISNOT_SV}
