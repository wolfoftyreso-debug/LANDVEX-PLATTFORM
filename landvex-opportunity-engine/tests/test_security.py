"""Tester för API-säkerhetslagret. Körs utan pytest:
python3 -m tests.test_security"""
from __future__ import annotations

from api.security import (ApiAuth, AuthError, Gate, Metrics, RateLimiter,
                          _parse_keys)


def test_key_parsing_and_validation():
    keys = _parse_keys("abc123:acme:analyst, xyz789:beta:partner")
    assert keys["abc123"].tenant == "acme"
    assert keys["abc123"].role == "analyst"
    assert keys["abc123"].key_id == "abc1…"        # aldrig hela nyckeln
    for bad in ("nyckel", "a:b", "a:b:superuser", "a:b:c:d"):
        try:
            _parse_keys(bad)
        except ValueError:
            continue
        raise AssertionError(f"Skulle ha avvisats: {bad}")


def test_open_mode_when_no_keys():
    auth = ApiAuth(keys_env="")
    assert not auth.enabled
    p = auth.authorize(None, "POST", "/v1/analyze")
    assert p.role == "admin" and p.tenant == "dev"


def test_auth_and_rbac():
    auth = ApiAuth(keys_env="k1:acme:analyst,k2:beta:partner,k3:ops:admin")
    assert auth.authorize("k1", "POST", "/v1/analyze").tenant == "acme"
    assert auth.authorize("k2", "POST", "/v1/ask").role == "partner"
    assert auth.authorize("k3", "GET", "/metrics").role == "admin"
    # Partner får inte skriva profiler; analyst får inte läsa metrics.
    cases = [(None, "POST", "/v1/analyze", 401),
             ("fel", "POST", "/v1/analyze", 401),
             ("k2", "POST", "/v1/profiles", 403),
             ("k2", "GET", "/v1/reports", 403),
             ("k1", "GET", "/metrics", 403),
             ("k1", "GET", "/v1/profiles/abc123", None if False else 200)]
    for key, method, path, expected in cases[:-1]:
        try:
            auth.authorize(key, method, path)
        except AuthError as e:
            assert e.status == expected, (path, e.status)
            continue
        raise AssertionError(f"Skulle ha nekats: {key} {method} {path}")
    # Prefixmatch: /v1/profiles/{id} ärver analyst-kravet.
    try:
        auth.authorize("k2", "GET", "/v1/profiles/abc123")
    except AuthError as e:
        assert e.status == 403
    else:
        raise AssertionError("Prefixmatch för RBAC saknas")


def test_rate_limiter_token_bucket():
    now = [0.0]
    rl = RateLimiter(per_minute=60, clock=lambda: now[0])
    for _ in range(60):
        rl.check("k")
    try:
        rl.check("k")
    except AuthError as e:
        assert e.status == 429
    else:
        raise AssertionError("Rate limit slog inte till")
    now[0] += 2.0                                   # 2 s ⇒ 2 nya tokens
    rl.check("k")
    rl.check("k")
    # Andra nycklar påverkas inte.
    rl.check("annan")


def test_metrics_snapshot():
    m = Metrics()
    for ms in (10.0, 20.0, 30.0, 400.0):
        m.observe("/v1/analyze", 200, ms)
    m.observe("/v1/scan?x=1", 500, 50.0)
    snap = m.snapshot()
    assert snap["requests_total"] == 5
    assert snap["errors_5xx_total"] == 1
    assert snap["requests_by_path"] == {"/v1/analyze": 4, "/v1/scan": 1}
    assert snap["latency_ms_p50"] is not None


def test_gate_end_to_end_audit(tmp_path=None):
    import json, os, tempfile
    path = os.path.join(tempfile.mkdtemp(), "audit.log")
    from api.security import AuditLog
    gate = Gate(auth=ApiAuth(keys_env="k1:acme:analyst"),
                limiter=RateLimiter(per_minute=100, clock=lambda: 0.0),
                audit=AuditLog(path=path))
    p, rid = gate.enter("k1", "POST", "/v1/analyze")
    gate.exit(p, rid, "POST", "/v1/analyze", 200, 12.5)
    with open(path, encoding="utf-8") as f:
        event = json.loads(f.readline())
    assert event["tenant"] == "acme" and event["status"] == 200
    assert event["request_id"] == rid
    assert "k1" not in json.dumps(event)            # nyckeln loggas aldrig


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
