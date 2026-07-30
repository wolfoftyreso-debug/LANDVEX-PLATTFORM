"""Integration layer toward the AAMOS Capability Platform (AAMOS Core).

AAMOS Core (:3100 in production) fronts the AAMOS Capability Platform
and its 12+ capability engines: Vision, Identity, Fraud,
Infrastructure, Safety, Inspection, Compliance, Reality, Change, Risk,
Evidence and Prediction. This module is the only place Landvex talks
to AAMOS.

Architecture principle: the deterministic engine core (engine/) NEVER
depends on AAMOS. AAMOS enrichment happens in the API layer only –
endpoints degrade honestly (status "ej_ansluten") when AAMOS_CORE_URL
is unset or AAMOS Core does not respond, and every engine/ result is
identical with or without AAMOS.

Zero runtime dependencies: stdlib only (urllib, json). The transport
is an injectable callable ``(method, url, body_dict|None) -> dict``
for deterministic tests, mirroring QuixzoomSource in
engine/datasources/adapters.py.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable
from urllib.parse import quote
from engine.datasources.faults import OUR_BUGS


def _xml_to_obj(text: str):
    """Best-effort XML/RSS → dict (AAMOS Core often returns RSS/XML in a
    `contents` field). Never raises; returns {"raw": text} on failure."""
    from engine.safexml import parse as _parse_xml
    try:
        root = _parse_xml(text)
    except OUR_BUGS:
        raise        # vårt fel, inte omvärldens – se faults.py
    except Exception:
        # Trasig, för stor eller DTD-bärande XML → ingen tolkning alls.
        return {"raw": text}

    def node(el):
        kids = list(el)
        tag = el.tag.split("}")[-1]
        if not kids:
            return tag, (el.text or "").strip()
        out: dict[str, Any] = {}
        for k in kids:
            ktag, kval = node(k)
            if ktag in out:
                if not isinstance(out[ktag], list):
                    out[ktag] = [out[ktag]]
                out[ktag].append(kval)
            else:
                out[ktag] = kval
        return tag, out
    _, obj = node(root)
    return obj if isinstance(obj, dict) else {"items": obj}


def _decode_body(text: str) -> dict:
    """Parse an AAMOS response body: JSON first; if a `contents` field
    carries XML/RSS, parse that too; plain XML → dict; else wrap raw."""
    text = text.strip()
    try:
        data = json.loads(text)
    except OUR_BUGS:
        raise        # vårt fel, inte omvärldens – se faults.py
    except Exception:
        # Inte JSON – kanske rå XML/RSS.
        return _xml_to_obj(text) if text[:1] == "<" else {"raw": text}
    if isinstance(data, dict):
        c = data.get("contents")
        if isinstance(c, str) and c.strip()[:1] == "<":
            data["contents_parsed"] = _xml_to_obj(c)
    return data if isinstance(data, dict) else {"items": data}


class AamosUnavailable(Exception):
    """AAMOS Core is not connected or did not respond."""


class AamosClient:
    """HTTP client for AAMOS Core.

    Base URL comes from AAMOS_CORE_URL (empty ⇒ not connected –
    reported honestly, never faked). Every method returns the parsed
    JSON dict from AAMOS Core and raises AamosUnavailable on any
    transport error or when not connected.
    """

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, str, dict | None], dict]
                 | None = None,
                 timeout: float = 5.0,
                 token: str | None = None, api_key: str | None = None):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("AAMOS_CORE_URL", ""))
        self._transport = transport or self._http
        self.timeout = timeout
        # Auth is configurable and optional. AAMOS Core gates every endpoint.
        # Set whichever scheme AAMOS-dev confirms (env or arg); none is logged:
        #   AAMOS_TOKEN     → Authorization: Bearer <token>
        #   AAMOS_API_KEY   → X-API-Key: <key>
        #   AAMOS_AUTH_HEADER + AAMOS_AUTH_VALUE → a fully custom header,
        #       e.g. AAMOS_AUTH_HEADER=X-Service-Token (covers non-standard
        #       schemes; the smoke test showed HS256/RS256 tokens are rejected,
        #       so the real credential must come from AAMOS Core, not be minted).
        self.token = token if token is not None else os.environ.get("AAMOS_TOKEN", "")
        self.api_key = (api_key if api_key is not None
                        else os.environ.get("AAMOS_API_KEY", ""))
        self.auth_header = os.environ.get("AAMOS_AUTH_HEADER", "")
        self.auth_value = os.environ.get("AAMOS_AUTH_VALUE", "")

    def auth_headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.api_key:
            h["X-API-Key"] = self.api_key
        if self.auth_header and self.auth_value:
            h[self.auth_header] = self.auth_value
        return h

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    # ── Transport ────────────────────────────────────────────────────
    def _http(self, method: str, url: str, body: dict | None) -> dict:
        data = None
        headers = {"Accept": "application/json", **self.auth_headers()}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return _decode_body(resp.read().decode("utf-8", "replace"))

    def _call(self, method: str, path: str,
              body: dict | None = None) -> dict:
        if not self.connected:
            raise AamosUnavailable(
                "AAMOS Core is not connected (set AAMOS_CORE_URL).")
        url = self.base_url.rstrip("/") + path
        try:
            return self._transport(method, url, body)
        except AamosUnavailable:
            raise
        except OUR_BUGS:
            # Ett fel i VÅR transportkod ska inte rapporteras som att
            # AAMOS är otillgängligt — då letar man på fel sida nätet.
            raise
        except Exception as e:
            raise AamosUnavailable(
                f"AAMOS Core request failed: {e}") from e

    # ── Identity engine ──────────────────────────────────────────────
    def identity_agents(self) -> dict:
        return self._call("GET", "/api/aamos/identity/agents")

    def check_permission(self, agent_id: str, action: str) -> dict:
        return self._call("POST", "/api/aamos/identity/check-permission",
                          {"agent_id": agent_id, "action": action})

    # ── Knowledge graph ──────────────────────────────────────────────
    def graph_stats(self) -> dict:
        return self._call("GET", "/api/aamos/graph/stats")

    def graph_search(self, q: str) -> dict:
        return self._call("GET", "/api/aamos/graph/search?q="
                          + quote(str(q), safe=""))

    # ── Analytics ────────────────────────────────────────────────────
    def entity_scores(self, entity_id: str) -> dict:
        return self._call("GET", "/api/aamos/analytics/scores/"
                          + quote(str(entity_id), safe=""))

    def intent_signals(self, company_id: str) -> dict:
        return self._call("GET", "/api/aamos/analytics/intent/"
                          + quote(str(company_id), safe=""))

    # ── Alerts & control plane ───────────────────────────────────────
    def alerts(self) -> dict:
        return self._call("GET", "/api/aamos/alerts")

    def control_plane_services(self) -> dict:
        return self._call("GET", "/api/aamos/control-plane/services")

    def health_summary(self) -> dict:
        return self._call("GET",
                          "/api/aamos/control-plane/health-summary")

    # ── Cognition ────────────────────────────────────────────────────
    def cognition_analysis(self, question: str,
                           context: dict | None = None) -> dict:
        body: dict[str, Any] = {"question": question}
        if context is not None:
            body["context"] = context
        return self._call("POST",
                          "/api/aamos/cognition/strategic-analysis",
                          body)

    def cognition_brief(self, topic: str) -> dict:
        return self._call("POST",
                          "/api/aamos/cognition/strategic-brief",
                          {"topic": topic})

    # ── Apollo ───────────────────────────────────────────────────────
    def apollo_contradictions(self) -> dict:
        return self._call("GET", "/api/aamos/apollo/contradictions")

    def apollo_intent(self) -> dict:
        return self._call("GET", "/api/aamos/apollo/intent")

    # ── Agent loop ───────────────────────────────────────────────────
    def agent_chat(self, message: str,
                   agent_id: str | None = None) -> dict:
        body: dict[str, Any] = {"message": message}
        if agent_id:
            body["agent_id"] = agent_id
        return self._call("POST", "/api/aamos/agent-loop/chat", body)

    # ── quiXzoom (reality collection, VIA AAMOS Core) ────────────────
    # quiXzoom är mission-baserat (missions + zoomer-submissions med
    # media), INTE en /v1/observations-endpoint. Fältdata når oss genom
    # AAMOS Core. Basvägen är konfigurerbar (AAMOS_QUIXZOOM_PATH) —
    # bekräftad live på server-2 den 2026-07-30 (infra/aws-svar-
    # 2026-07-30-b.md): den aktiva routen är /api/quixzoom/missions,
    # inte den tidigare gissade /api/qz/missions.
    QUIXZOOM_PATH = os.environ.get(
        "AAMOS_QUIXZOOM_PATH", "/api/quixzoom/missions")

    def quixzoom_missions(self, lat: float, lon: float,
                          radius_km: float = 5.0) -> dict:
        """quiXzoom-missions/submissions nära en punkt, via AAMOS Core.
        Fältnamn enligt verklig modell: id, title, location{lat,lng},
        status, required_media, reward."""
        path = (f"{self.QUIXZOOM_PATH}?lat={lat}&lon={lon}"
                f"&radius_km={radius_km}")
        return self._call("GET", path)

    def register_service(self, name: str, port: int,
                         endpoints: list[str] | None = None) -> dict:
        """Registrera denna tjänst i AAMOS service registry
        (/api/services/register). Best-effort – anroparen sväljer fel."""
        return self._call("POST", "/api/services/register",
                          {"name": name, "port": port,
                           "endpoints": endpoints or []})

    # ── Honest status (same ids as the rest of the platform) ─────────
    def status(self) -> dict:
        if not self.connected:
            return {"source": "aamos_core", "status": "ej_ansluten",
                    "notis_en": "Client ready – set AAMOS_CORE_URL to "
                                "connect the AAMOS Capability "
                                "Platform."}
        return {"source": "aamos_core", "status": "ok",
                "notis_en": "Connected to the AAMOS Capability "
                            "Platform."}


# ── Endpoint-hjälpare (delas av api/dev_server.py och api/main.py) ──
# Alla hjälpare degraderar ärligt (status "ej_ansluten") – ett AAMOS-
# fel får aldrig fälla en endpoint.

def _aamos_degraded() -> dict:
    return {"source": "aamos_core", "status": "ej_ansluten",
            "notis_en": "AAMOS Core did not respond – reported as not "
                        "connected until it recovers."}


def _aamos_list(raw, key: str) -> list:
    if isinstance(raw, dict):
        val = raw.get(key, [])
        return val if isinstance(val, list) else [val]
    return list(raw) if isinstance(raw, list) else []


def platform_status(client, resolver, store,
                    build_health, source_status) -> dict:
    out = {"opportunity_engine": build_health(resolver, store),
           "aamos": client.status()}
    if client.connected:
        try:
            out["aamos_health"] = client.health_summary()
            out["aamos_services"] = client.control_plane_services()
        except AamosUnavailable:
            out.pop("aamos_health", None)
            out.pop("aamos_services", None)
            out["aamos"] = _aamos_degraded()
    return out


def watch(client, resolver, source_status) -> dict:
    paused = [k["source"] for k in source_status(resolver)
              if k["status"] == "pausad"]
    out = {"alerts": [], "paused_sources": paused,
           "aamos": client.status()}
    if not client.connected:
        out["notis_en"] = ("No AAMOS alerts – the AAMOS Capability "
                           "Platform is not connected (set "
                           "AAMOS_CORE_URL). Local source status is "
                           "still reported.")
        return out
    try:
        out["alerts"] = _aamos_list(client.alerts(), "alerts")
        out["notis_en"] = ("Alerts live from the AAMOS Capability "
                           "Platform.")
    except AamosUnavailable:
        out["aamos"] = _aamos_degraded()
        out["notis_en"] = ("AAMOS Core did not respond – no alerts "
                           "available right now.")
    return out


def agents(client) -> dict:
    out = {"agents": [], "aamos": client.status()}
    if not client.connected:
        out["notis_en"] = ("No agents – the AAMOS Capability Platform "
                           "is not connected (set AAMOS_CORE_URL).")
        return out
    try:
        out["agents"] = _aamos_list(client.identity_agents(), "agents")
    except AamosUnavailable:
        out["aamos"] = _aamos_degraded()
        out["notis_en"] = ("AAMOS Core did not respond – no agents "
                           "available right now.")
    return out


def agent_chat_safe(client, message: str,
                    agent_id: str | None = None) -> dict:
    if client.connected:
        try:
            return client.agent_chat(message, agent_id=agent_id)
        except AamosUnavailable:
            return {"svar_en": "The AAMOS agent loop did not respond "
                               "– try again shortly.",
                    "aamos": _aamos_degraded()}
    return {"svar_en": "The AAMOS agent loop is not connected "
                       "(set AAMOS_CORE_URL).",
            "aamos": client.status()}


def cognition_brief_safe(client, topic: str) -> dict:
    if client.connected:
        try:
            return client.cognition_brief(topic)
        except AamosUnavailable:
            return {"svar_en": "AAMOS cognition did not respond – try "
                               "again shortly.",
                    "aamos": _aamos_degraded()}
    return {"svar_en": "AAMOS cognition is not connected "
                       "(set AAMOS_CORE_URL).",
            "aamos": client.status()}
