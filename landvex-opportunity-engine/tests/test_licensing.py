"""Tester för licens-/paketlagret. Körs utan pytest:
python3 -m tests.test_licensing"""
from __future__ import annotations

from api.catalog import API_CATALOG
from api.licensing import (ADDONS, PLANS, plans_catalog,
                           required_capability, resolve_capabilities,
                           upgrade_hint_en)
from api.security import ApiAuth, AuthError, RateLimiter, _parse_keys


def test_plans_and_addons_are_valid_data():
    assert set(PLANS) == {"free", "pro", "enterprise"}
    free, pro, ent = (set(PLANS[p]["capabilities"])
                      for p in ("free", "pro", "enterprise"))
    assert free < pro < ent                            # strikt nivåtrappa
    for p in PLANS.values():
        assert p["rate_limit_per_min"] > 0 and p["ingar_en"]
        if p["pris_manad"] is not None:
            assert set(p["pris_manad"]) == {"SEK", "EUR", "USD"}
    for a in ADDONS.values():
        assert a["capabilities"] and a["pris_manad"]["SEK"] > 0
    kat = plans_catalog()
    assert len(kat["plans"]) == 3 and len(kat["tillagg"]) == 5
    assert "list price" in kat["prisnot_en"].lower() or \
           "example" in kat["prisnot_en"].lower()      # ärlig prismärkning


def test_every_engine_endpoint_has_a_capability():
    for eng in API_CATALOG["engines"]:
        for ep in eng["endpoints"]:
            if ep["path"] in ("/health",):
                continue
            assert required_capability(ep["path"]) is not None, ep["path"]


def test_capability_resolution_and_addons():
    caps = resolve_capabilities("free")
    assert "core" in caps and "workforce" not in caps
    caps2 = resolve_capabilities("free", ("workforce",))
    assert "workforce" in caps2                        # à la carte-modul
    assert "opportunity" not in caps2
    for bad in [("guld", ()), ("free", ("raketpaket",))]:
        try:
            resolve_capabilities(*bad)
        except ValueError:
            continue
        raise AssertionError(f"Skulle ha avvisats: {bad}")


def test_key_format_with_plan_and_addons():
    keys = _parse_keys("k1:acme:analyst:free:workforce|intelligence_map,"
                       "k2:beta:admin")
    assert keys["k1"].plan == "free"
    assert keys["k1"].addons == ("workforce", "intelligence_map")
    assert "workforce" in keys["k1"].capabilities
    assert keys["k2"].plan == "enterprise"             # bakåtkompatibelt


def test_plan_enforcement_in_authorize():
    auth = ApiAuth(keys_env="fri:acme:analyst:free,"
                            "proff:acme:analyst:pro,"
                            "wf:beta:analyst:free:workforce")
    assert auth.authorize("fri", "POST", "/v1/ask")           # core OK
    assert auth.authorize("proff", "POST", "/v1/scan")        # pro OK
    assert auth.authorize("wf", "POST", "/v1/workforce/forecast")  # tillägg OK
    for key, method, path in [("fri", "POST", "/v1/scan"),
                              ("fri", "POST", "/v1/workforce/forecast"),
                              ("wf", "POST", "/v1/scan"),
                              ("proff", "GET", "/v1/agent-manifest")]:
        try:
            auth.authorize(key, method, path)
        except AuthError as e:
            assert e.status == 403
            assert "/v1/plans" in e.message_en         # uppgraderingshänvisning
            continue
        raise AssertionError(f"Skulle ha spärrats: {key} {path}")


def test_rate_limit_per_plan():
    now = [0.0]
    rl = RateLimiter(per_minute=300, clock=lambda: now[0])
    free_cap = PLANS["free"]["rate_limit_per_min"]
    for _ in range(free_cap):
        rl.check("fri-nyckel", free_cap)
    try:
        rl.check("fri-nyckel", free_cap)
    except AuthError as e:
        assert e.status == 429 and "plans" in e.message_en
    else:
        raise AssertionError("Free-taket slog inte till")
    # Pro-nyckel har eget, högre tak.
    for _ in range(free_cap + 10):
        rl.check("pro-nyckel", PLANS["pro"]["rate_limit_per_min"])


def test_upgrade_hint_mentions_unlocking_products():
    hint = upgrade_hint_en("workforce")
    assert "Pro" in hint and "Workforce" in hint


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
