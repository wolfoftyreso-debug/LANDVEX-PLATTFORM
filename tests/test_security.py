"""Tester för API-säkerhetslagret. Körs utan pytest:
python3 -m tests.test_security"""
from __future__ import annotations

from api.security import (ApiAuth, AuthError, Gate, Metrics, RateLimiter,
                          _b64url, _parse_keys, jwt_decode, jwt_encode)


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


def test_jwt_roundtrip():
    claims = {"sub": "svc-aamos", "tenant": "acme", "role": "analyst",
              "plan": "pro", "exp": 2000}
    tok = jwt_encode(claims, "s3cret")
    assert tok.count(".") == 2
    assert jwt_decode(tok, "s3cret", now=1000.0) == claims
    # Utan exp: giltig oavsett klocka.
    evig = jwt_encode({"tenant": "acme"}, "s3cret")
    assert jwt_decode(evig, "s3cret", now=9e12)["tenant"] == "acme"


def test_jwt_rejections():
    tok = jwt_encode({"tenant": "acme", "exp": 2000}, "s3cret")
    h, p, s = tok.split(".")

    def avvisas(token, secret="s3cret", now=1000.0):
        try:
            jwt_decode(token, secret, now=now)
        except ValueError:
            return
        raise AssertionError(f"Skulle ha avvisats: {token[:40]}…")

    # Manipulerad signatur och fel hemlighet.
    flip = ("B" if s[0] == "A" else "A") + s[1:]
    avvisas(f"{h}.{p}.{flip}")
    avvisas(tok, secret="fel-hemlighet")
    # Manipulerad payload (signaturen matchar inte längre).
    import json
    p2 = _b64url(json.dumps({"tenant": "annan"}).encode())
    avvisas(f"{h}.{p2}.{s}")
    # Utgången token (injicerad klocka – deterministiskt).
    avvisas(tok, now=2000.0)
    avvisas(tok, now=3000.0)
    # alg=none och andra algoritmer avvisas även med "giltig" HMAC.
    import hashlib, hmac
    for alg in ("none", "HS512", "RS256"):
        h2 = _b64url(json.dumps({"alg": alg, "typ": "JWT"}).encode())
        sig = hmac.new(b"s3cret", f"{h2}.{p}".encode(),
                       hashlib.sha256).digest()
        avvisas(f"{h2}.{p}.{_b64url(sig)}")
    # Trasig struktur.
    avvisas("bara-en-strang")
    avvisas("a.b")
    avvisas("!!!.%%%.###")


def test_jwt_authorize_principal_and_capabilities():
    auth = ApiAuth(keys_env="k1:acme:analyst", jwt_secret="topsecret")
    tok = jwt_encode({"sub": "svc-aamos", "tenant": "beta",
                      "role": "analyst", "plan": "pro"}, "topsecret")
    p = auth.authorize(f"Bearer {tok}", "POST", "/v1/analyze")
    assert p.tenant == "beta" and p.role == "analyst"
    assert p.key_id == "svc-aamos"                 # sub → key_id
    assert p.plan == "pro" and "opportunity" in p.capabilities
    # Case-insensitivt prefix och rått token utan prefix fungerar.
    assert auth.authorize(f"bearer {tok}", "POST", "/v1/analyze").tenant == "beta"
    assert auth.authorize(tok, "POST", "/v1/analyze").tenant == "beta"
    # Defaultar: sub→"jwt", role→analyst, plan→free, addons→().
    minimal = jwt_encode({"tenant": "gamma"}, "topsecret")
    p2 = auth.authorize(minimal, "POST", "/v1/ask")
    assert (p2.key_id, p2.role, p2.plan, p2.addons) == \
        ("jwt", "analyst", "free", ())
    # Addons ger kapabiliteter (free + workforce-tillägg).
    atok = jwt_encode({"tenant": "gamma", "plan": "free",
                       "addons": ["workforce"]}, "topsecret")
    p3 = auth.authorize(atok, "POST", "/v1/workforce/forecast")
    assert "workforce" in p3.capabilities
    # API-nyckelvägen är intakt när båda lägena är konfigurerade.
    assert auth.authorize("k1", "POST", "/v1/analyze").tenant == "acme"


def test_jwt_authorize_enforcement_and_errors():
    auth = ApiAuth(keys_env="k1:acme:analyst", jwt_secret="topsecret")

    def nekas(credential, method, path, status, fragment=None):
        try:
            auth.authorize(credential, method, path)
        except AuthError as e:
            assert e.status == status, (path, e.status, e.message_en)
            if fragment:
                assert fragment in e.message_en, e.message_en
            return e
        raise AssertionError(f"Skulle ha nekats: {method} {path}")

    mk = lambda **c: "Bearer " + jwt_encode(c, "topsecret")
    # RBAC: partner-JWT får inte skriva profiler eller läsa rapporter;
    # analyst-JWT får inte läsa metrics. Samma 403 som för nycklar.
    nekas(mk(tenant="b", role="partner", plan="pro"),
          "POST", "/v1/profiles", 403, "insufficient")
    nekas(mk(tenant="b", role="partner", plan="pro"),
          "GET", "/v1/reports", 403)
    nekas(mk(tenant="b", role="analyst", plan="enterprise"),
          "GET", "/metrics", 403)
    # Plan-kapabilitet: free saknar opportunity → 403 med upgrade-hint.
    nekas(mk(tenant="b", plan="free"), "POST", "/v1/scan", 403,
          "/v1/plans")
    # Saknad tenant → 401.
    nekas(mk(sub="x", role="analyst"), "POST", "/v1/ask", 401, "tenant")
    # Okänd plan/roll → 401 med ärligt felmeddelande.
    nekas(mk(tenant="b", plan="platina"), "POST", "/v1/ask", 401,
          "Unknown plan")
    nekas(mk(tenant="b", role="superuser"), "POST", "/v1/ask", 401,
          "Unknown role")
    # Utgången token → 401 (exp=1 är alltid passerad).
    nekas(mk(tenant="b", exp=1), "POST", "/v1/ask", 401, "expired")
    # Manipulerad signatur → 401.
    tok = jwt_encode({"tenant": "b"}, "topsecret")
    h, p, s = tok.split(".")
    flip = ("B" if s[0] == "A" else "A") + s[1:]
    nekas(f"Bearer {h}.{p}.{flip}", "POST", "/v1/ask", 401)
    # Ingen JWT-hemlighet konfigurerad → 401, ärligt besked.
    auth2 = ApiAuth(keys_env="k1:acme:analyst", jwt_secret="")
    try:
        auth2.authorize(f"Bearer {tok}", "POST", "/v1/ask")
    except AuthError as e:
        assert e.status == 401
        assert "not configured" in e.message_en
    else:
        raise AssertionError("JWT utan hemlighet skulle ha nekats")
    # Nyckel-auth opåverkad i nyckel-enbart-läge.
    assert auth2.authorize("k1", "POST", "/v1/analyze").tenant == "acme"


def test_jwt_gate_audit_never_logs_token():
    import json, os, tempfile
    from api.security import AuditLog
    path = os.path.join(tempfile.mkdtemp(), "audit.log")
    gate = Gate(auth=ApiAuth(keys_env="k1:acme:analyst",
                             jwt_secret="topsecret"),
                limiter=RateLimiter(per_minute=100, clock=lambda: 0.0),
                audit=AuditLog(path=path))
    tok = jwt_encode({"sub": "svc-aamos", "tenant": "beta",
                      "role": "analyst", "plan": "pro"}, "topsecret")
    p, rid = gate.enter(f"Bearer {tok}", "POST", "/v1/analyze")
    gate.exit(p, rid, "POST", "/v1/analyze", 200, 3.2)
    with open(path, encoding="utf-8") as f:
        event = json.loads(f.readline())
    assert event["tenant"] == "beta" and event["key_id"] == "svc-aamos"
    dumped = json.dumps(event)
    assert tok not in dumped and tok.split(".")[2] not in dumped



# ── Revisionsfynd: grindar som såg ut att gälla ──────────────────────────
def test_a_valid_api_key_containing_dots_still_authenticates():
    """En nyckel som råkar se ut som en JWT är fortfarande en nyckel.

    _extract_jwt kände igen formen "två punkter" och skickade credentialen
    till JWT-vägen, som avvisade den med "JWT authentication is not
    configured". En korrekt konfigurerad nyckel kunde alltså aldrig logga
    in. Exakt uppslag går före heuristik.
    """
    from api.security import ApiAuth
    a = ApiAuth(keys_env="ab.cd.ef:acme:admin:pro", jwt_secret="")
    p = a.authorize("ab.cd.ef", "GET", "/v1/markets")
    assert p.tenant == "acme" and p.plan == "pro"
    # och en okänd credential med samma form ger fortfarande 401
    try:
        a.authorize("xx.yy.zz", "GET", "/v1/markets")
    except AuthError as e:
        assert e.status == 401
    else:
        raise AssertionError("okänd nyckel släpptes igenom")


def test_a_rate_limit_of_zero_means_zero():
    """`if per_minute` gjorde 0 falsy → taket blev det globala (300/min).
    Ett tak som tyst blir sin motsats är värre än inget tak."""
    from api.security import RateLimiter
    rl = RateLimiter(per_minute=300)
    try:
        rl.check("blocked", 0)
    except AuthError as e:
        assert e.status == 429
    else:
        raise AssertionError("ett tak på 0 släppte igenom ett anrop")
    # None betyder fortfarande "använd det globala taket"
    rl.check("normal", None)
    try:
        rl.check("negative", -1)
    except ValueError:
        pass
    else:
        raise AssertionError("negativt tak accepterades")


def test_one_percentile_definition_in_the_whole_codebase():
    """Mätgrinden godkänner bygget, /metrics beskriver driften. Räknar de
    olika beror svaret på vem som frågade."""
    from api import security
    from engine.stats import percentile
    from scripts.perf_budget import percentile as gate_percentile
    assert percentile is gate_percentile is security.percentile


def test_nobody_hand_rolls_a_percentile_next_to_the_shared_one():
    """Första versionen av testet ovan kollade de tre jag råkade känna
    till. En fjärde satt kvar i scripts/measure_api och skrev p95
    12982 ms där grinden räknade 830,7 på samma tal — och det var
    mätningens siffra som stod i CI-loggen.

    Det här testet letar efter MÖNSTRET i stället för efter namnen.
    """
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parent.parent
    suspects = []
    pattern = re.compile(
        r"sorted\([^)]*\)\s*\[[^\]]*(0\.9|0\.5|95|99|50)[^\]]*\]"
        r"|\[\s*int\([^)]*len\([^)]*\)\s*\*\s*0\.\d+")
    for path in list((root / "engine").rglob("*.py")) \
            + list((root / "api").rglob("*.py")) \
            + list((root / "scripts").rglob("*.py")):
        if path.name in ("stats.py",):
            continue                  # den kanoniska definitionen bor här
        for i, line in enumerate(
                path.read_text(encoding="utf-8").split("\n"), 1):
            if pattern.search(line):
                suspects.append(f"{path.relative_to(root)}:{i}: {line.strip()}")
    assert not suspects, (
        "Egenhändiga percentilberäkningar vid sidan av engine.stats."
        "percentile:\n  " + "\n  ".join(suspects))


def test_the_latency_window_is_bounded_without_copying_every_call():
    from api.security import Metrics
    import collections
    m = Metrics()
    for i in range(Metrics.WINDOW + 500):
        m.observe("/x", 200, float(i))
    assert isinstance(m._latencies, collections.deque)
    assert m._latencies.maxlen == Metrics.WINDOW
    assert len(m._latencies) == Metrics.WINDOW
    assert m.requests == Metrics.WINDOW + 500     # räknaren tappar inget


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
