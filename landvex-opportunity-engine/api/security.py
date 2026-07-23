"""Säkerhet & observability för API-lagret (endast stdlib).

Delas av dev-servern och FastAPI-appen så att beteendet är identiskt:

  AUTENTISERING  Två lägen, kan kombineras (samma authorize()-
                 kontrakt – credential är det servern läst ur
                 headern, rå nyckel eller "Bearer <jwt>"):
                 (1) API-nycklar via LANDVEX_API_KEYS
                     ("nyckel:tenant:roll[:plan[:tillägg|tillägg]]"),
                     headern X-API-Key.
                 (2) JWT bearer-tokens (HS256, AAMOS-standard) med
                     hemligheten LANDVEX_JWT_SECRET. Claims:
                     sub→key_id (default "jwt"), tenant (KRÄVS),
                     role (default "analyst"), plan (default
                     "free"), addons (lista, default []), exp
                     (epoksekunder). Tom hemlighet = JWT-auth
                     avstängd (Bearer ger då 401).
                 Båda tomma = öppet läge (lokal utveckling).
                 OIDC/Cognito ersätter nyckellagret i AWS-fasen.
  RBAC           Roller: admin > analyst > partner. Partner är
                 read/analyze-only (får inte skriva profiler eller
                 läsa andras rapportlistor).
  RATE LIMITING  Token bucket per nyckel (LANDVEX_RATE_LIMIT anrop/
                 minut, default 300; öppet läge begränsas per klient-
                 nyckel "anon").
  TENANT         Varje nyckel hör till en tenant – id:t följer med i
                 audit- och requestloggar (grunden för isolering när
                 lagret får tenant-kolumner, se readiness-review).
  AUDIT/LOGG     Strukturerade JSON-rader till stdout (requestlogg)
                 och LANDVEX_AUDIT_LOG (revisionslogg, default
                 landvex-audit.log, "off" stänger av).
  METRICS        Räknare + latenspercentiler i minnet, exponeras på
                 /metrics (kräver admin när auth är på).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass

_ROLE_RANK = {"partner": 0, "analyst": 1, "admin": 2}

# Minsta roll per känslig operation; allt annat kräver lägsta rollen.
_MIN_ROLE = {
    ("POST", "/v1/profiles"): "analyst",
    ("GET", "/v1/profiles"): "analyst",
    ("GET", "/v1/reports"): "analyst",
    ("GET", "/metrics"): "admin",
    ("GET", "/v1/audit"): "admin",
}


class AuthError(Exception):
    def __init__(self, status: int, message_en: str):
        super().__init__(message_en)
        self.status = status
        self.message_en = message_en


from api import licensing


# ── JWT (HS256) – stdlib-implementation, AAMOS-standard ──────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def jwt_encode(claims: dict, secret: str) -> str:
    """Signera claims som en HS256-JWT (header.payload.signature)."""
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), f"{h}.{p}".encode(),
                   hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


def jwt_decode(token: str, secret: str, now: float | None = None) -> dict:
    """Verifiera och läs en HS256-JWT. ValueError med ärligt engelskt
    meddelande vid fel alg, trasig struktur, ogiltig signatur eller
    passerad exp (epoksekunder; `now` injicerbar för tester)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed JWT: expected three dot-separated "
                         "segments.")
    h_b64, p_b64, s_b64 = parts
    try:
        header = json.loads(_b64url_decode(h_b64))
    except Exception:
        raise ValueError("Malformed JWT: header is not valid "
                         "base64url-encoded JSON.")
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ValueError("Unsupported JWT algorithm: only HS256 is "
                         "accepted.")
    expected = hmac.new(secret.encode(), f"{h_b64}.{p_b64}".encode(),
                        hashlib.sha256).digest()
    try:
        actual = _b64url_decode(s_b64)
    except Exception:
        raise ValueError("Malformed JWT: signature is not valid "
                         "base64url.")
    if not hmac.compare_digest(expected, actual):
        raise ValueError("Invalid JWT signature.")
    try:
        claims = json.loads(_b64url_decode(p_b64))
    except Exception:
        raise ValueError("Malformed JWT: payload is not valid "
                         "base64url-encoded JSON.")
    if not isinstance(claims, dict):
        raise ValueError("Malformed JWT: payload must be a JSON object.")
    exp = claims.get("exp")
    if exp is not None:
        try:
            exp_s = float(exp)
        except (TypeError, ValueError):
            raise ValueError("Malformed JWT: 'exp' must be a number "
                             "(epoch seconds).")
        current = now if now is not None else time.time()
        if current >= exp_s:
            raise ValueError("JWT has expired.")
    return claims


def _extract_jwt(credential: str) -> str | None:
    """Bearer-detektering: skala ev. 'Bearer '-prefix (case-
    insensitivt); en rest med exakt två punkter och base64url-
    avkodbar header behandlas som JWT, annars API-nyckel."""
    token = credential.strip()
    if token[:7].lower() == "bearer ":
        token = token[7:].strip()
    if token.count(".") != 2:
        return None
    try:
        _b64url_decode(token.split(".", 1)[0])
    except Exception:
        return None
    return token


@dataclass(frozen=True)
class Principal:
    tenant: str
    role: str
    key_id: str          # maskerat nyckel-id för loggar, aldrig nyckeln
    plan: str = "enterprise"
    addons: tuple = ()
    capabilities: frozenset = frozenset()


def _parse_keys(raw: str) -> dict[str, Principal]:
    """Format: nyckel:tenant:roll[:plan[:tillägg|tillägg]].
    Utan plan ⇒ enterprise (bakåtkompatibelt)."""
    out: dict[str, Principal] = {}
    for entry in filter(None, (e.strip() for e in raw.split(","))):
        parts = entry.split(":")
        if not 3 <= len(parts) <= 5 or parts[2] not in _ROLE_RANK:
            raise ValueError(f"Invalid LANDVEX_API_KEYS entry: {entry!r} "
                             f"(format key:tenant:role[:plan[:addons]], "
                             f"role ∈ {sorted(_ROLE_RANK)})")
        key, tenant, role = parts[0], parts[1], parts[2]
        plan = parts[3] if len(parts) >= 4 and parts[3] else "enterprise"
        addons = tuple(filter(None, parts[4].split("|"))) if len(parts) == 5 else ()
        caps = licensing.resolve_capabilities(plan, addons)   # validerar
        out[key] = Principal(tenant, role,
                             f"{key[:4]}…" if len(key) > 4 else "…",
                             plan, addons, caps)
    return out


class ApiAuth:
    def __init__(self, keys_env: str | None = None,
                 jwt_secret: str | None = None):
        raw = keys_env if keys_env is not None else os.environ.get(
            "LANDVEX_API_KEYS", "")
        self.keys = _parse_keys(raw)
        self.jwt_secret = (jwt_secret if jwt_secret is not None
                           else os.environ.get("LANDVEX_JWT_SECRET", ""))
        self.enabled = bool(self.keys) or bool(self.jwt_secret)

    _OPEN = Principal("dev", "admin", "open", "enterprise", (),
                      licensing.resolve_capabilities("enterprise"))

    def authorize(self, credential: str | None, method: str,
                  path: str) -> Principal:
        """credential = det servern läst ur headern: rå API-nyckel
        (X-API-Key) eller ett Bearer-värde (Authorization)."""
        if not self.enabled:
            return self._OPEN
        if not credential:
            if self.jwt_secret:
                raise AuthError(401, "Credentials required: API key "
                                     "(header X-API-Key) or JWT bearer "
                                     "token (header Authorization).")
            raise AuthError(401, "API key required (header X-API-Key).")
        token = _extract_jwt(credential)
        if token is not None:
            p = self._principal_from_jwt(token)
        else:
            p = self.keys.get(credential)
            if p is None:
                raise AuthError(401, "Invalid API key.")
        return self._enforce(p, method, path)

    def _principal_from_jwt(self, token: str) -> Principal:
        if not self.jwt_secret:
            raise AuthError(401, "JWT authentication is not configured "
                                 "on this server.")
        try:
            claims = jwt_decode(token, self.jwt_secret)
        except ValueError as e:
            raise AuthError(401, str(e))
        tenant = claims.get("tenant")
        if not tenant or not isinstance(tenant, str):
            raise AuthError(401, "JWT is missing the required 'tenant' "
                                 "claim.")
        role = claims.get("role", "analyst")
        if role not in _ROLE_RANK:
            raise AuthError(401, f"Unknown role in JWT: {role!r}. "
                                 f"Valid roles: "
                                 f"{', '.join(sorted(_ROLE_RANK))}.")
        plan = claims.get("plan", "free")
        raw_addons = claims.get("addons", [])
        if not isinstance(raw_addons, (list, tuple)):
            raise AuthError(401, "JWT claim 'addons' must be a list.")
        addons = tuple(str(a) for a in raw_addons)
        try:
            caps = licensing.resolve_capabilities(plan, addons)
        except ValueError as e:
            raise AuthError(401, str(e))
        key_id = str(claims.get("sub") or "jwt")
        return Principal(tenant, role, key_id, plan, addons, caps)

    def _enforce(self, p: Principal, method: str, path: str) -> Principal:
        """Gemensam RBAC- + kapabilitetskontroll för båda auth-lägena."""
        base = path.split("?")[0].rstrip("/")
        # Prefixmatch så /v1/profiles/{id} ärver /v1/profiles-kravet.
        needed = "partner"
        for (m, prefix), role in _MIN_ROLE.items():
            if m == method and base.startswith(prefix):
                needed = max(needed, role, key=lambda r: _ROLE_RANK[r])
        if _ROLE_RANK[p.role] < _ROLE_RANK[needed]:
            raise AuthError(403, f"Role '{p.role}' has insufficient "
                                 f"permissions for {method} {base}.")
        # Paketkontroll: planen/tilläggen måste ge endpointens kapabilitet.
        cap = licensing.required_capability(base)
        if cap and cap not in p.capabilities:
            raise AuthError(403, f"The '{p.plan}' plan does not include "
                                 f"{base}. {licensing.upgrade_hint_en(cap)}")
        return p


class RateLimiter:
    """Token bucket per nyckel-id."""

    def __init__(self, per_minute: int | None = None, clock=time.monotonic):
        self.capacity = float(per_minute if per_minute is not None else
                              int(os.environ.get("LANDVEX_RATE_LIMIT", "300")))
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def check(self, key_id: str, per_minute: float | None = None) -> None:
        cap = float(per_minute) if per_minute else self.capacity
        now = self._clock()
        with self._lock:
            tokens, ts = self._buckets.get(key_id, (cap, now))
            tokens = min(cap, tokens + (now - ts) * cap / 60.0)
            if tokens < 1.0:
                raise AuthError(429, "Too many requests for this plan "
                                     "tier – try again shortly or upgrade "
                                     "(see /v1/plans).")
            self._buckets[key_id] = (tokens - 1.0, now)


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.requests = 0
        self.errors = 0
        self.by_path: dict[str, int] = {}
        self._latencies: list[float] = []      # senaste 1000
        self.started = time.time()

    def observe(self, path: str, status: int, ms: float) -> None:
        with self._lock:
            self.requests += 1
            if status >= 500:
                self.errors += 1
            base = path.split("?")[0]
            self.by_path[base] = self.by_path.get(base, 0) + 1
            self._latencies.append(ms)
            if len(self._latencies) > 1000:
                self._latencies = self._latencies[-1000:]

    def snapshot(self) -> dict:
        with self._lock:
            lat = sorted(self._latencies)
            pct = (lambda p: round(lat[min(len(lat) - 1,
                                           int(p * len(lat)))], 1)) if lat else (lambda p: None)
            return {"uptime_s": round(time.time() - self.started, 1),
                    "requests_total": self.requests,
                    "errors_5xx_total": self.errors,
                    "latency_ms_p50": pct(0.50),
                    "latency_ms_p95": pct(0.95),
                    "requests_by_path": dict(sorted(self.by_path.items())),
                    "rate_limit_per_min": None}

    def to_prometheus(self, sources: list[dict] | None = None) -> str:
        """Prometheus text-exposition av samma data (?format=prometheus)."""
        s = self.snapshot()
        lines = [
            "# TYPE landvex_uptime_seconds gauge",
            f"landvex_uptime_seconds {s['uptime_s']}",
            "# TYPE landvex_requests_total counter",
            f"landvex_requests_total {s['requests_total']}",
            "# TYPE landvex_errors_5xx_total counter",
            f"landvex_errors_5xx_total {s['errors_5xx_total']}",
        ]
        for q, key in (("0.5", "latency_ms_p50"), ("0.95", "latency_ms_p95")):
            if s[key] is not None:
                lines.append(f'landvex_latency_ms{{quantile="{q}"}} {s[key]}')
        for path, n in s["requests_by_path"].items():
            lines.append(f'landvex_requests_by_path_total{{path="{path}"}} {n}')
        for k in sources or []:
            up = 1 if k["status"] == "ok" else 0
            lines.append(f'landvex_source_up{{source="{k["source"]}"}} {up}')
        return "\n".join(lines) + "\n"


class AuditLog:
    """Revisionslogg som JSON-rader. Requestlogg går till stdout."""

    def __init__(self, path: str | None = None):
        p = path if path is not None else os.environ.get(
            "LANDVEX_AUDIT_LOG", "landvex-audit.log")
        self.path = None if p.lower() in ("off", "0", "") else p
        self._lock = threading.Lock()

    def write(self, event: dict) -> None:
        line = json.dumps(event, ensure_ascii=False)
        print(line, file=sys.stdout, flush=True)          # strukturerad logg
        if self.path:
            with self._lock, open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def tail(self, limit: int = 100) -> list[dict]:
        """Senaste händelserna (för GET /v1/audit, kräver admin)."""
        if not self.path or not os.path.exists(self.path):
            return []
        with self._lock, open(self.path, encoding="utf-8") as f:
            rader = f.readlines()[-max(1, min(limit, 1000)):]
        out = []
        for r in rader:
            try:
                out.append(json.loads(r))
            except json.JSONDecodeError:
                continue
        return out



class MonthlyQuota:
    """Månadskvot per tenant och plan (Bernts pristabell: Free 100,
    Growth 10 000, Enterprise obegränsat). In-memory per process –
    nollställs vid omstart; persistent metering är en dokumenterad
    uppföljning. Klockan är injicerbar för deterministiska tester."""

    def __init__(self, clock=None):
        self._clock = clock or time.time
        self._used: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def check(self, tenant: str, quota: int | None) -> None:
        if quota is None:
            return
        month = time.strftime("%Y-%m", time.gmtime(self._clock()))
        key = (tenant, month)
        # Check-and-increment måste vara atomiskt: annars kan två samtidiga
        # anrop båda läsa n=quota-1 och båda släppas igenom (kvotöverskott).
        with self._lock:
            n = self._used.get(key, 0)
            if n >= quota:
                raise AuthError(429, f"Monthly quota reached ({quota} calls/"
                                     f"month on this plan) – resets next "
                                     f"month, or upgrade (see /v1/plans).")
            self._used[key] = n + 1


class Gate:
    """Samlad ingång: auth → rate limit → audit + metrics."""

    def __init__(self, auth: ApiAuth | None = None,
                 limiter: RateLimiter | None = None,
                 metrics: Metrics | None = None,
                 audit: AuditLog | None = None):
        self.auth = auth or ApiAuth()
        self.limiter = limiter or RateLimiter()
        self.metrics = metrics or Metrics()
        self.audit = audit or AuditLog()
        self.quota = MonthlyQuota()

    def enter(self, api_key: str | None, method: str, path: str) -> tuple[Principal, str]:
        principal = self.auth.authorize(api_key, method, path)
        plan_limit = licensing.PLANS.get(principal.plan, {}).get(
            "rate_limit_per_min")
        self.limiter.check(principal.key_id, plan_limit)
        self.quota.check(principal.tenant, licensing.PLANS.get(
            principal.plan, {}).get("quota_per_month"))
        return principal, uuid.uuid4().hex[:12]

    def exit(self, principal: Principal | None, request_id: str,
             method: str, path: str, status: int, ms: float) -> None:
        self.metrics.observe(path, status, ms)
        self.audit.write({
            "ts": round(time.time(), 3), "request_id": request_id,
            "tenant": principal.tenant if principal else None,
            "role": principal.role if principal else None,
            "key_id": principal.key_id if principal else None,
            "method": method, "path": path.split("?")[0],
            "status": status, "duration_ms": round(ms, 1),
        })
