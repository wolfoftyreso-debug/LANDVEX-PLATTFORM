"""Ta med svaret till dina egna verktyg — utan att tappa förbehållen.

Beslutet `export_findings` i `engine/offering.py` stod som `planned`:
"Consultants and analysts working in Excel or GIS." Det är den vanligaste
invändningen i kategorin, och den var inte byggd.

**Det farliga med export är inte formatet, det är vad som faller bort på
vägen.** Ett Opportunity Score i en CSV-fil ser ut som ett mätvärde. Det
är det inte: det är ett viktat index på delvis simulerad data, med en
täckningsgrad och en lista förbehåll som hela plattformen är byggd för
att aldrig svälja. Släpper vi ut talet utan dem har vi byggt precis den
sortens verktyg vi säger att vi inte är.

Därför bär **varje** exportformat sin proveniens i själva filen:

  * CSV: förbehållen ligger som `#`-kommentarrader först. `pandas`
    läser dem med `comment="#"`, Excel visar dem, och den som klipper
    bort dem gör det medvetet.
  * NDJSON: första raden är ett `_landvex`-objekt med samma innehåll.
  * GeoJSON: ett `landvex`-medlemsfält på FeatureCollection (GeoJSON
    tillåter främmande medlemmar).

Format vi INTE kan leverera vägras med namngivet skäl i stället för att
approximeras: PDF och XLSX kräver renderingsberoenden som kärnan inte
får ha, och Parquet ett kolumnbibliotek. En CSV med filändelsen .xlsx är
en lögn med ett Excel-ikon på.

Nytt dataset = en ny rad i `DATASETS`. Ingen motorändring.

Rent stdlib.
"""
from __future__ import annotations

import datetime as _dt
import io as _io
import json

from engine.markets import DEFAULT_MARKET
from engine.version import ENGINE_VERSION


class ExportRefused(ValueError):
    """Exporten gick inte att göra, och varför."""


# ── Format ──────────────────────────────────────────────────────────────
FORMATS: dict[str, dict] = {
    "csv": {"media_type": "text/csv; charset=utf-8", "suffix": "csv",
            "label_en": "CSV (Excel, R, pandas)",
            "provenance_en": "Caveats ride along as leading # comment "
                             "lines. pandas: read_csv(path, comment='#')."},
    "ndjson": {"media_type": "application/x-ndjson", "suffix": "ndjson",
               "label_en": "NDJSON (one object per line)",
               "provenance_en": "The first line is a _landvex object with "
                                "version, source state and caveats."},
    "geojson": {"media_type": "application/geo+json", "suffix": "geojson",
                "label_en": "GeoJSON (QGIS, ArcGIS, Mapbox)",
                "provenance_en": "Caveats sit in a 'landvex' member on the "
                                 "FeatureCollection.",
                "needs_coords": True},
}

# Vad vi inte gör, och varför. Att stå med i katalogen är poängen: den
# som letar efter PDF ska hitta beskedet, inte tystnaden.
REFUSED_FORMATS: dict[str, str] = {
    "pdf": "A PDF needs a rendering library, and engine/ takes no "
           "dependencies. Export CSV or GeoJSON and lay it out where the "
           "report is written — a fake PDF is worse than none.",
    "xlsx": "A real .xlsx is a zip of XML parts. Renaming a CSV to .xlsx "
            "makes Excel warn the user that the file is corrupt. Use CSV; "
            "Excel opens it natively.",
    "parquet": "Parquet needs a columnar library (pyarrow). It belongs in "
               "the API layer or a job, never in the dependency-free core.",
    "shapefile": "Shapefile is several binary files with a 10-character "
                 "column-name limit that would silently truncate our "
                 "headers. GeoJSON carries the same geometry and keeps the "
                 "names.",
}


# ── Datamängderna ───────────────────────────────────────────────────────
def _kol(*par: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(par)


def _rader_scan(p: dict, tenant: str) -> tuple[list[dict], dict]:
    from engine.profile import profile_from_dict
    from engine.scan import scan

    profil = p.get("profile") or {"vertical_id": p.get("vertical", "gym")}
    r = scan(profile_from_dict(profil), top_n=int(p.get("top_n", 10)),
             market=p.get("market") or DEFAULT_MARKET)
    rader = [{
        "rank": h["rank"], "region": h["kommun"], "region_code": h["kommun_kod"],
        "location": h["lage_en"], "lat": h["lat"], "lon": h["lon"],
        "opportunity_score": h["opportunity_score"],
        "rank_score": h["rank_score"], "confidence": h["confidence"],
        "risk_index": h["risk_index"], "risk_level": h["risk_level"],
        "data_coverage": h["data_coverage"],
        "time_window_months": h["time_window_months"],
        "why": " | ".join(h["motivering_en"][:2]),
    } for h in r["hotspots"]]
    return rader, {"market": r["market"], "vertical": r["vertical_label_en"],
                   "caveats_en": r["caveats_en"],
                   "scanned": r["kommuner_scanned"]}


def _rader_gaps(p: dict, tenant: str) -> tuple[list[dict], dict]:
    from engine.gaps import gap_analysis

    r = gap_analysis(p.get("vertical", "gym"), market=p.get("market") or DEFAULT_MARKET,
                     top_n=int(p.get("top_n", 10)))
    rader = [{
        "region": g["kommun"], "region_code": g["kommun_kod"],
        "lat": g["lat"], "lon": g["lon"],
        "imbalance_score": g["obalans_score"], "class": g["klass"],
        "demand": g["efterfragan"], "supply_deficit": g["utbudsunderskott"],
        "development": g["utveckling"], "direction": g["utveckling_riktning"],
        "opportunity_score": g["opportunity_score"],
        "data_coverage": g["data_coverage"], "why": g["narrativ_en"],
    } for g in r["obalanser"]]
    return rader, {"market": r["market"], "vertical": r["vertical_label_en"],
                   "caveats_en": r["caveats_en"],
                   "summary_en": r["sammanfattning_en"]}


def _rader_workforce(p: dict, tenant: str) -> tuple[list[dict], dict]:
    from engine.workforce import national_map

    r = national_map(p.get("occupation_id", "elektriker"),
                     int(p.get("target_year", 2035)),
                     market=p.get("market") or DEFAULT_MARKET)
    rader = [{
        "region": k["kommun"], "region_code": k["kommun_kod"],
        "lat": k["lat"], "lon": k["lon"],
        "need_forecast": k["behov_prognos"], "shortage": k["brist"],
        "band": k["band"], "demand": k["efterfragan"], "trend": k["trend"],
        "confidence": k["konfidens"],
    } for k in r["kommuner"]]
    return rader, {"market": r["market"], "occupation": r["label_en"],
                   "target_year": r["malar"], "caveats_en": r["caveats_en"]}


def _rader_compliance(p: dict, tenant: str) -> tuple[list[dict], dict]:
    from engine import inspections as I

    r = I.report(tenant, p.get("today", ""))
    rader = [{
        "asset_id": x["asset"]["id"], "asset": x["asset"].get("label_en", ""),
        "kind": x["asset"].get("kind", ""),
        "address": x["asset"].get("address", ""),
        "lat": x["asset"].get("lat"), "lon": x["asset"].get("lon"),
        "routine_id": x.get("routine_id", ""), "status": x["status"],
        "days_overdue": x.get("days_overdue", 0),
        "last_checked": x.get("last_checked", ""),
        "last_verdict": x.get("last_verdict", ""),
        "next_due": x.get("next_due", ""), "why": x.get("why_en", ""),
    } for x in r["rows"]]
    return rader, {"as_of": r["as_of"], "share_current": r["share_current"],
                   "caveats_en": [r["cannot_en"]]}


def _rader_exceptions(p: dict, tenant: str) -> tuple[list[dict], dict]:
    from engine import inspections as I

    r = I.exception_feed(tenant, p.get("today", ""))
    rader = [{
        "asset_id": x["asset"]["id"], "asset": x["asset"].get("label_en", ""),
        "address": x["asset"].get("address", ""),
        "lat": x["asset"].get("lat"), "lon": x["asset"].get("lon"),
        "status": x["status"], "days_overdue": x.get("days_overdue", 0),
        "next_due": x.get("next_due", ""), "why": x.get("why_en", ""),
    } for x in r["exceptions"]]
    return rader, {"as_of": r["as_of"], "of_total": r["of_total"],
                   "caveats_en": []}


def _rader_freshness(p: dict, tenant: str) -> tuple[list[dict], dict]:
    from engine import infrastructure as INF
    from engine import inspections as I

    obs = I.all_observations(tenant)
    rader = []
    for a in I.all_assets(tenant):
        if a.get("kind") not in INF.OBJECT_TYPES:
            continue
        s = INF.status(a["id"], a["kind"], obs)
        for f in s["fields"]:
            rader.append({
                "object_id": a["id"], "object": a.get("label_en", ""),
                "kind": a["kind"], "address": a.get("address", ""),
                "lat": a.get("lat"), "lon": a.get("lon"),
                "field": f["observation_id"],
                "field_label": f["label_en"],
                "freshness": f["freshness"],
                # Tomt value för stale är POÄNGEN, inte ett hål i filen:
                # det utgångna värdet står under last_known som historik.
                "value": f["value"] if f["value"] is not None else "",
                "last_known": f.get("last_known", ""),
                "age_minutes": (f["age_minutes"]
                                if f["age_minutes"] is not None else ""),
                "fresh_for_minutes": f.get("fresh_for_minutes", ""),
                "confidence_band": f["confidence"]["band"],
                "why": f["why_en"],
            })
    return rader, {"caveats_en": [
        "value is empty for stale and never-verified fields on purpose: "
        "an expired reading is history under last_known, never current "
        "state, and nothing is estimated between observations.",
        "Confidence is a band, never a score — a single observer "
        "network stays at 'weak' however often it looks.",
    ]}


DATASETS: tuple[dict, ...] = (
    {"id": "hotspots", "label_en": "Market sweep — ranked locations",
     "capability": "opportunity", "answers_from": "/v1/scan",
     "params_en": "profile (or vertical), market, top_n",
     "rows": _rader_scan,
     "columns": _kol(("rank", "Rank"), ("region", "Region"),
                     ("opportunity_score", "Opportunity score"),
                     ("confidence", "Confidence"),
                     ("risk_index", "Risk index"))},
    {"id": "imbalances", "label_en": "Gap analysis — demand vs supply",
     "capability": "opportunity", "answers_from": "/v1/gaps",
     "params_en": "vertical, market, top_n",
     "rows": _rader_gaps,
     "columns": _kol(("region", "Region"),
                     ("imbalance_score", "Imbalance score"),
                     ("class", "Class"))},
    {"id": "workforce_shortage", "label_en": "Workforce — shortage by region",
     "capability": "workforce", "answers_from": "/v1/workforce/map",
     "params_en": "occupation_id, target_year, market",
     "rows": _rader_workforce,
     "columns": _kol(("region", "Region"), ("shortage", "Shortage"),
                     ("band", "Band"))},
    {"id": "compliance", "label_en": "Compliance record — your own objects",
     "capability": "asset_inspections",
     "answers_from": "/v1/inspections/compliance",
     "params_en": "today (optional)", "tenant_scoped": True,
     "rows": _rader_compliance,
     "columns": _kol(("asset_id", "Object"), ("status", "Status"),
                     ("next_due", "Next due"))},
    {"id": "exceptions", "label_en": "Exception feed — what needs someone",
     "capability": "asset_inspections",
     "answers_from": "/v1/inspections/exceptions",
     "params_en": "today (optional)", "tenant_scoped": True,
     "rows": _rader_exceptions,
     "columns": _kol(("asset_id", "Object"), ("status", "Status"),
                     ("days_overdue", "Days overdue"))},
    {"id": "infrastructure_freshness",
     "label_en": "Reality freshness — field by field, with its age",
     "capability": "asset_inspections",
     "answers_from": "/v1/infrastructure/status",
     "params_en": "none (tenant-scoped)", "tenant_scoped": True,
     "rows": _rader_freshness,
     "columns": _kol(("object_id", "Object"), ("field", "Field"),
                     ("freshness", "Freshness"), ("value", "Value"),
                     ("last_known", "Last known (history)"))},
)

_BY_ID = {d["id"]: d for d in DATASETS}


def catalog() -> dict:
    """Vad som går att exportera, i vilka format — och vad som inte gör det."""
    return {
        "datasets": [{k: v for k, v in d.items() if k != "rows"}
                     for d in DATASETS],
        "formats": [{"id": f, **{k: v for k, v in spec.items()}}
                    for f, spec in FORMATS.items()],
        "refused": [{"id": f, "why_en": why}
                    for f, why in REFUSED_FORMATS.items()],
        "principle_en": (
            "Every export carries its own provenance. A score in a "
            "spreadsheet looks like a measurement; it is a weighted index "
            "on partly simulated data, and the caveats travel with the "
            "file rather than staying behind on the screen."),
    }


# ── Skrivarna ───────────────────────────────────────────────────────────
def _meta(dataset: dict, extra: dict, antal: int) -> dict:
    m = {
        "produced_by": "Landvex",
        "engine_version": ENGINE_VERSION,
        "dataset": dataset["id"],
        "answers_from": dataset["answers_from"],
        "rows": antal,
        "exported_at": _dt.datetime.now(_dt.timezone.utc)
                          .replace(microsecond=0).isoformat(),
        "read_this_en": (
            "These numbers are decision support, not measurements. Scores "
            "are weighted indices with a stated data coverage; anything "
            "sourced from mock is labelled so at the source. Do not "
            "multiply a score onward as if it were an observation."),
    }
    m.update({k: v for k, v in extra.items() if k != "caveats_en"})
    m["caveats_en"] = list(extra.get("caveats_en") or [])
    return m


def _csv(rader: list[dict], meta: dict) -> str:
    import csv

    buf = _io.StringIO()
    for rad in _meta_lines(meta):
        buf.write(f"# {rad}\n")
    if rader:
        w = csv.DictWriter(buf, fieldnames=list(rader[0]),
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rader)
    return buf.getvalue()


def _meta_lines(meta: dict) -> list[str]:
    rader = [f"Landvex export · {meta['dataset']} · engine "
             f"{meta['engine_version']} · {meta['exported_at']}",
             meta["read_this_en"]]
    for k, v in meta.items():
        if k in ("dataset", "engine_version", "exported_at", "read_this_en",
                 "caveats_en", "produced_by"):
            continue
        rader.append(f"{k}: {v}")
    rader += [f"caveat: {c}" for c in meta["caveats_en"]]
    return rader


def _ndjson(rader: list[dict], meta: dict) -> str:
    ut = [json.dumps({"_landvex": meta}, ensure_ascii=False)]
    ut += [json.dumps(r, ensure_ascii=False) for r in rader]
    return "\n".join(ut) + "\n"


def _geojson(rader: list[dict], meta: dict) -> str:
    features = []
    for r in rader:
        lat, lon = r.get("lat"), r.get("lon")
        if lat is None or lon is None:
            continue          # en feature utan geometri är inte en feature
        egen = {k: v for k, v in r.items() if k not in ("lat", "lon")}
        features.append({"type": "Feature",
                         "geometry": {"type": "Point",
                                      "coordinates": [lon, lat]},
                         "properties": egen})
    return json.dumps({"type": "FeatureCollection", "features": features,
                       "landvex": meta}, ensure_ascii=False, indent=1) + "\n"


_SKRIVARE = {"csv": _csv, "ndjson": _ndjson, "geojson": _geojson}


def export(dataset_id: str, format: str = "csv", params: dict | None = None,
           *, tenant: str = "") -> dict:
    """Kör datamängden och skriv ut den i valt format.

    `tenant` är obligatorisk för de datamängder som är kundens egna. Utan
    den vägrar exporten i stället för att råka skriva ut allas rader —
    det är exakt den sortens misstag som bara upptäcks efteråt.
    """
    d = _BY_ID.get(dataset_id)
    if d is None:
        raise ExportRefused(
            f"unknown dataset {dataset_id!r}. Available: "
            f"{', '.join(sorted(_BY_ID))}")
    if format in REFUSED_FORMATS:
        raise ExportRefused(f"{format}: {REFUSED_FORMATS[format]}")
    if format not in FORMATS:
        raise ExportRefused(
            f"unknown format {format!r}. Available: "
            f"{', '.join(FORMATS)}; refused on purpose: "
            f"{', '.join(REFUSED_FORMATS)}")
    if d.get("tenant_scoped") and not tenant:
        raise ExportRefused(
            f"dataset {dataset_id!r} holds one customer's own objects and "
            f"needs a tenant. Exporting without one would write every "
            f"customer's rows into the same file.")

    rader, extra = d["rows"](dict(params or {}), tenant)
    meta = _meta(d, extra, len(rader))
    if FORMATS[format].get("needs_coords") and rader and \
            not any(r.get("lat") is not None for r in rader):
        raise ExportRefused(
            f"dataset {dataset_id!r} has no coordinates in this result, so "
            f"a GeoJSON export would be an empty map. Use csv or ndjson.")
    innehall = _SKRIVARE[format](rader, meta)
    stamp = meta["exported_at"][:10]
    return {
        "dataset": dataset_id, "format": format,
        "filename": f"landvex-{dataset_id}-{stamp}.{FORMATS[format]['suffix']}",
        "media_type": FORMATS[format]["media_type"],
        "row_count": len(rader), "content": innehall, "meta": meta,
        "provenance_en": FORMATS[format]["provenance_en"],
    }
