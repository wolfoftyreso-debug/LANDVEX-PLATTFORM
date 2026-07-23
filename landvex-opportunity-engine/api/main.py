"""LANDVEX Opportunity Engine – produktions-API (FastAPI).

Körs efter `pip install -r requirements.txt`:
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Motorimporten är beroendefri; endast API-lagret kräver FastAPI.
För en beroendefri utvecklingsserver, se api/dev_server.py.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from engine.datasources.adapters import production_sources
from engine.datasources.base import Resolver
from engine.datasources.mock import MockSource
from engine.models import Location
from engine.scoring import analyze
from engine.verticals import VERTICALS

app = FastAPI(title="LANDVEX Opportunity Engine", version="0.2.0")

# Verkliga källor först, mock som fallback per signal.
# LANDVEX_LIVE=0 stänger av live-källor (demo/offline/test).
_LIVE = os.environ.get("LANDVEX_LIVE", "1") != "0"
RESOLVER = Resolver((production_sources() if _LIVE else []) + [MockSource()])


class AnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    vertical: str
    address: str = ""
    radius_minutes: int = Field(10, ge=1, le=60)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/verticals")
def verticals():
    return [{"id": v.id, "label_sv": v.label_sv,
             "factors": [{"id": f.id, "label_sv": f.label_sv, "weight": f.weight}
                         for f in v.factors]}
            for v in VERTICALS.values()]


@app.post("/v1/analyze")
def analyze_location(req: AnalyzeRequest):
    if req.vertical not in VERTICALS:
        raise HTTPException(status_code=422,
                            detail=f"Okänd vertikal: {req.vertical}")
    loc = Location(lat=req.lat, lon=req.lon, address=req.address,
                   radius_minutes=req.radius_minutes)
    return analyze(loc, req.vertical, resolver=RESOLVER).to_dict()
