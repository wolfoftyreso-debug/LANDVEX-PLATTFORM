"""Deterministisk mockdatakälla.

Seedas på koordinater, så samma plats alltid ger samma rapport.
Värdena korreleras via en "urbanitetsfaktor" (u) så att en tät plats
får högre flöden, högre hyror, fler konkurrenter osv. – realistiskt
nog för demo, produktutveckling och tester.

Ersätts/kompletteras i produktion av riktiga adaptrar (scb, movement,
permits, places) via Resolver-kedjan.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from ..models import Location, SignalValue
from .base import DataSource


def _seed(location: Location, vertical_id: str) -> int:
    key = f"{round(location.lat, 3)}:{round(location.lon, 3)}:{vertical_id}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)


class MockSource(DataSource):
    name = "mock"

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        rng = random.Random(_seed(location, vertical_id))
        u = rng.uniform(0.25, 1.0)          # urbanitet
        g = rng.uniform(-1.0, 7.0)          # tillväxtklimat, %
        income = 80 + u * 25 + rng.uniform(-8, 12)

        pop = int(3000 + u * 16000 * rng.uniform(0.7, 1.2))
        foot = int(400 + u * 6500 * rng.uniform(0.6, 1.3))
        f_morning = int(60 + u * 620 * rng.uniform(0.5, 1.4))
        f_midday = int(80 + u * 750 * rng.uniform(0.5, 1.4))
        f_afternoon = int(50 + u * 560 * rng.uniform(0.3, 1.4))
        f_evening = int(40 + u * 520 * rng.uniform(0.3, 1.5))

        # Konkurrentbild → härlett tryck. Fullbokade och lågt betyg = svagare
        # effektiv konkurrens (kapacitet/kvalitet saknas i utbudet).
        n_comp = max(0, int(rng.gauss(u * 6.5, 1.8)))
        full_booked = min(n_comp, int(rng.random() * (n_comp * 0.5 + 0.9)))
        low_rated = min(n_comp - full_booked, int(rng.random() * (n_comp * 0.45 + 0.8)))
        premium = min(n_comp - full_booked - low_rated, rng.randint(0, 1))
        effective = max(0.0, n_comp - 0.7 * full_booked - 0.6 * low_rated - 0.4 * premium)
        demand_units = (pop / 1600.0) * rng.uniform(0.8, 1.2)   # grov efterfrågeproxy
        gap = demand_units / max(effective, 0.5)

        vals = {
            "pop_radius": pop,
            "population_total": int(14000 + u * 180000 * rng.uniform(0.5, 1.5)),
            "pop_growth_pct": round(g, 1),
            "income_index": round(income, 1),
            "age_20_45_share": round(18 + u * 22 + rng.uniform(-4, 4), 1),
            "families_share": round(14 + (1 - u) * 18 + rng.uniform(-4, 5), 1),
            "share_65plus": round(14 + (1 - u) * 14 + rng.uniform(-3, 4), 1),
            "residential_density": int(150 + u * 2200 * rng.uniform(0.6, 1.2)),
            "foot_traffic": foot,
            "target_match_pct": round(30 + u * 35 + rng.uniform(-8, 12), 0),
            "flow_morning": f_morning, "flow_midday": f_midday,
            "flow_afternoon": f_afternoon, "flow_evening": f_evening,
            "commuter_flow": int(300 + u * 7000 * rng.uniform(0.5, 1.3)),
            "parking_score": round(max(0, min(10, 9.5 - u * 6 + rng.uniform(-1.5, 1.5))), 1),
            "transit_score": round(max(0, min(10, 1.5 + u * 8 + rng.uniform(-1.5, 1.5))), 1),
            "competition_pressure": round(min(10.0, effective * 1.3), 1),
            "provider_gap": round(min(3.0, gap), 2),
            "detached_homes": int(200 + (1 - u) * 4200 * rng.uniform(0.5, 1.3)),
            "building_permits": int(6 + (0.4 + 0.6 * abs(g) / 7) * 160 * rng.uniform(0.3, 1.1)),
            "renovation_index": int(25 + (1 - u) * 50 + rng.uniform(0, 25)),
            "avg_building_age": int(rng.uniform(12, 85)),
            "ev_per_capita": int(10 + income * 0.55 * rng.uniform(0.5, 1.2)),
            "business_density": int(15 + u * 55 * rng.uniform(0.5, 1.2)),
            "office_workers": int(200 + u * 7000 * rng.uniform(0.4, 1.3)),
            "hotel_beds": int(u * 900 * rng.uniform(0.0, 1.2)),
            "tourism_index": int(u * 75 * rng.uniform(0.2, 1.2)),
            "event_days": int(u * 55 * rng.uniform(0.1, 1.2)),
            "detail_plans": int(max(0, rng.gauss(2 + g, 2.2))),
            "development_m2": int(max(0, rng.gauss(30 + g * 14, 35))),
            "infra_invest": int(max(0, rng.gauss(120 + g * 45, 120))),
            "cars_per_1000": int(300 + (1 - u) * 260 + rng.uniform(-40, 40)),
            "avg_car_age": round(8 + (1 - u) * 5 + rng.uniform(-1.5, 1.5), 1),
            "pets_per_1000": int(120 + (1 - u) * 220 * rng.uniform(0.6, 1.2)),
            "logistics_access": round(max(0.0, min(10.0, 2 + u * 5 + g * 0.4 +
                                                   rng.uniform(-2, 2))), 1),
            "insurance_index": round(65 + income * 0.35 + rng.uniform(-8, 8), 0),
            "care_supply": round(rng.uniform(1, 9), 1),
            "vacancy_rate": round(max(0.5, 11 - u * 7 + rng.uniform(-2, 3)), 1),
            "rent_index": round(85 + u * 55 + rng.uniform(-8, 10), 0),
            "crime_index": round(80 + u * 35 + rng.uniform(-12, 18), 0),
            "climate_risk_index": round(max(5, min(90, 20 + (1 - u) * 15 +
                                                   rng.uniform(0, 35))), 0),
        }

        signals = {sid: SignalValue(sid, vals[sid], source=self.name, quality=0.4)
                   for sid in signal_ids if sid in vals}
        extras: dict[str, Any] = {
            "competitors": {"count": n_comp, "full_booked": full_booked,
                            "low_rated": low_rated, "premium": premium,
                            "effective": round(effective, 1)},
            "demand_units": round(demand_units, 1),
            "flows": {"morning": f_morning, "midday": f_midday,
                      "afternoon": f_afternoon, "evening": f_evening},
        }
        return signals, extras
