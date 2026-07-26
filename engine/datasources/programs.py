"""Programs registry adapter — real support programs for Opportunity Intel.

Turns the support-program ARCHETYPES in engine/opportunity_intel.py into
real programs (with real amounts, deadlines and eligibility) when a live
registry is connected — EU Funding & Tenders, Vinnova, Energimyndigheten,
Tillväxtverket, regional funds. Same Resolver/degradation contract as the
SCB and quiXzoom adapters:

  * stdlib only (urllib, json, xml) — belongs to engine/, runs in Lambda.
  * transport is injectable → deterministic fixture tests, no network.
  * NOT connected until LANDVEX_PROGRAMS_URL is set → callers fall back to
    the archetypes honestly; a registry error never breaks a response.
  * every real record is marked source="registry"; amounts/deadlines that
    come from the feed are real, everything derived stays labelled.

Contract (what LANDVEX_PROGRAMS_URL must return). Either:
  (a) JSON already in the normalized shape — a list, or {"programs":[...]}
      of records with the fields in `normalize_record` below, or
  (b) an RSS/Atom feed of calls/grants — each <item>/<entry> becomes a
      record (title→label_en, link→url, summary→raw_summary_en, the amount
      parsed from the text if present).
Provider-specific field mapping MUST be confirmed against the live feed
(run scripts/programs_probe.py) — exactly like the quiXzoom mission shape.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable
from .faults import OUR_BUGS

_UA = "landvex-opportunity-engine/programs"


def _http_transport(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _rss_items(text: str) -> list[dict]:
    """Best-effort RSS/Atom → list of {title, link, summary, published}."""
    from ..safexml import parse as _parse_xml
    try:
        root = _parse_xml(text)
    except OUR_BUGS:
        raise        # vårt fel, inte omvärldens – se faults.py
    except Exception:
        return []
    items: list[dict] = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        rec: dict[str, str] = {}
        for child in el:
            ct = child.tag.split("}")[-1]
            if ct == "title":
                rec["title"] = (child.text or "").strip()
            elif ct == "link":
                rec["link"] = (child.get("href") or child.text or "").strip()
            elif ct in ("description", "summary", "content"):
                rec["summary"] = (child.text or "").strip()
            elif ct in ("pubDate", "updated", "published"):
                rec["published"] = (child.text or "").strip()
        if rec:
            items.append(rec)
    return items


def normalize_record(raw: dict) -> dict[str, Any]:
    """Map a raw feed record to the normalized program shape. Unknown fields
    are left null/empty — never fabricated."""
    label = raw.get("label_en") or raw.get("title") or raw.get("name") or ""
    return {
        "id": str(raw.get("id") or raw.get("guid") or label)[:120],
        "label_en": label,
        "provider": raw.get("provider") or raw.get("source") or "registry",
        "amount_local": raw.get("amount_local"),        # [lo, hi] or None
        "currency": raw.get("currency"),
        "deadline": raw.get("deadline") or raw.get("published"),
        "eligibility_en": raw.get("eligibility_en") or [],
        "documents_en": raw.get("documents_en") or [],
        "verticals": raw.get("verticals") or [],        # [] = all trades
        "url": raw.get("url") or raw.get("link") or "",
        "raw_summary_en": raw.get("raw_summary_en") or raw.get("summary") or "",
        "source": "registry",
    }


class ProgramsClient:
    """Client for a live support-programs registry. Not connected until
    LANDVEX_PROGRAMS_URL is set — reported honestly, never faked."""

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 6.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_PROGRAMS_URL", ""))
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def fetch_programs(self, lat: float, lon: float,
                       vertical_id: str) -> list[dict[str, Any]]:
        """Normalized program records near a point for a vertical. Raises
        nothing that isn't caught by the caller; empty list on soft failure."""
        if not self.connected:
            return []
        url = (f"{self.base_url}{'&' if '?' in self.base_url else '?'}"
               f"lat={lat}&lon={lon}&vertical={vertical_id}")
        text = self._transport(url, self.timeout).strip()
        raws: list[dict]
        try:
            data = json.loads(text)
            raws = data.get("programs", data) if isinstance(data, dict) else data
            if not isinstance(raws, list):
                raws = []
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:
            raws = _rss_items(text) if text[:1] == "<" else []
        # Filter to the vertical when the record declares trades.
        out = []
        for r in raws:
            if not isinstance(r, dict):
                continue
            rec = normalize_record(r)
            if rec["verticals"] and vertical_id not in rec["verticals"]:
                continue
            if rec["label_en"]:
                out.append(rec)
        return out

    def status(self) -> dict[str, Any]:
        if not self.connected:
            return {"source": "programs_registry", "status": "ej_ansluten",
                    "notis_en": "Set LANDVEX_PROGRAMS_URL to connect a live "
                                "programs registry (EU Funding & Tenders, "
                                "Vinnova, Energimyndigheten, regional funds)."}
        return {"source": "programs_registry", "status": "ok",
                "notis_en": "Connected to a live programs registry."}
