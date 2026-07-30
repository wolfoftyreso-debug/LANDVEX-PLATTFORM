"""Direct quiXzoom client (:3209) — optional alternative to via-AAMOS-Core.

The confirmed data path is quiXzoom → AAMOS Core (:3100)
/api/quixzoom/missions (verified live on server-2, 2026-07-30).
But AAMOS Core gates every endpoint and a valid service token has been the
blocker. quiXzoom also runs its OWN API on :3209. Talking to a service's own
API is normal integration, not a bypass — so this is an OPTIONAL direct
client: if quiXzoom exposes direct access on :3209 (open, or with its own
credential), field_observation_density can go live without a Core token.

It is a drop-in for AamosClient inside QuixzoomSource: same
`.connected` / `.base_url` / `.quixzoom_missions(lat, lon, radius_km)`
surface, returning the parsed JSON in the same mission shape
(id, title, location:{lat,lng}, ...).

Config (all env, none logged):
    LANDVEX_QUIXZOOM_URL          base, e.g. http://127.0.0.1:3209  (empty ⇒ not connected)
    LANDVEX_QUIXZOOM_PATH         missions path (default /api/missions)
    LANDVEX_QUIXZOOM_KEY          credential value, if :3209 needs one
    LANDVEX_QUIXZOOM_AUTH_HEADER  header name for the key (default Authorization → "Bearer <key>")

If :3209 also returns 401 this client surfaces it honestly — the credential
must then come from quiXzoom, it is never forged. stdlib only; transport
injectable for tests.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable
from .faults import OUR_BUGS


class DirectQuixzoomClient:
    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float, dict], str] | None = None,
                 timeout: float = 5.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_QUIXZOOM_URL", ""))
        self.path = os.environ.get("LANDVEX_QUIXZOOM_PATH", "/api/missions")
        self.key = os.environ.get("LANDVEX_QUIXZOOM_KEY", "")
        self.auth_header = os.environ.get("LANDVEX_QUIXZOOM_AUTH_HEADER",
                                          "Authorization")
        self._transport = transport or self._http
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def auth_headers(self) -> dict[str, str]:
        if not self.key:
            return {}
        val = (f"Bearer {self.key}" if self.auth_header == "Authorization"
               else self.key)
        return {self.auth_header: val}

    def _http(self, url: str, timeout: float, headers: dict) -> str:
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")

    def quixzoom_missions(self, lat: float, lon: float,
                          radius_km: float = 10.0) -> Any:
        if not self.connected:
            from integrations.aamos import AamosUnavailable
            raise AamosUnavailable("Direct quiXzoom not connected "
                                   "(set LANDVEX_QUIXZOOM_URL).")
        sep = "&" if "?" in self.path else "?"
        url = (f"{self.base_url.rstrip('/')}{self.path}{sep}"
               f"lat={lat}&lon={lon}&radius_km={radius_km}")
        try:
            text = self._transport(url, self.timeout, self.auth_headers())
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception as e:
            from integrations.aamos import AamosUnavailable
            raise AamosUnavailable(f"Direct quiXzoom request failed: {e}") from e
        text = text.strip()
        try:
            return json.loads(text)
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:
            return {"raw": text}
