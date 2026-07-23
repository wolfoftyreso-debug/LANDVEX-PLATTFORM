"""Förklaringslager.

Gör scoren begriplig: varje faktor får en läsbar svensk mening byggd
på råvärdena, i samma stil som konceptdokumentet
("12 400 personer inom 10 minuter", "63 % av förbipasserande ...").
Ett score ingen kan förklara tappar förtroende – detta lager är
därför lika viktigt som själva beräkningen.
"""
from __future__ import annotations

from typing import Any

from .models import Location, SignalValue


def sv_num(x: float | int) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def _v(values: dict[str, SignalValue], sid: str) -> float | None:
    sv = values.get(sid)
    return sv.value if sv else None


def factor_narrative(factor_id: str, location: Location,
                     values: dict[str, SignalValue], extras: dict[str, Any]) -> str:
    v = lambda sid: _v(values, sid)

    if factor_id == "kundunderlag" and v("pop_radius") is not None:
        return f"{sv_num(v('pop_radius'))} people within {location.radius_minutes} minutes."
    if factor_id == "synlighet" and v("foot_traffic") is not None:
        return f"About {sv_num(v('foot_traffic'))} people pass the premises per day."
    if factor_id == "matchning" and v("target_match_pct") is not None:
        return f"{int(v('target_match_pct'))}% of passers-by belong to the target group."
    if factor_id == "kopkraft" and v("income_index") is not None:
        idx = v("income_index")
        rel = ("above" if idx > 102 else
               ("on par with" if idx >= 98 else "below"))
        return f"Mean income {rel} the national average (index {int(idx)})."
    if factor_id == "tillvaxt" and v("pop_growth_pct") is not None:
        g = v("pop_growth_pct")
        riktning = "growing" if g >= 0 else "shrinking"
        return f"The population is {riktning} by {abs(g)}%."

    if factor_id == "konkurrens" and "competitors" in extras:
        c = extras["competitors"]
        huvud = (f"{c['count']} competitors in the area" if c["count"] != 1
                 else "1 competitor in the area")
        delar = [huvud]
        if c["full_booked"]:
            delar.append(f"{c['full_booked']} fully booked")
        if c["low_rated"]:
            delar.append(f"{c['low_rated']} with weak reviews")
        if c["premium"]:
            delar.append(f"{c['premium']} in the premium segment")
        return ". ".join([delar[0]] + [d.capitalize() for d in delar[1:]]) + "."

    if factor_id in ("marknadsutrymme",) and v("provider_gap") is not None:
        gap = v("provider_gap")
        if gap >= 1.3:
            return "Demand exceeds current supply – clear market headroom."
        if gap >= 0.95:
            return "Demand and supply in balance."
        return "Supply likely exceeds demand – saturated market."

    if factor_id == "byggaktivitet" and v("building_permits") is not None:
        return f"{sv_num(v('building_permits'))} building permits granted in the last 12 months."
    if factor_id == "fastighetsbestand" and v("detached_homes") is not None:
        return (f"{sv_num(v('detached_homes'))} detached homes in the area, "
                f"average age about {int(v('avg_building_age') or 0)} years.")
    if factor_id == "elektrifiering" and v("ev_per_capita") is not None:
        return f"{int(v('ev_per_capita'))} EVs per 1,000 residents – growing charging demand."
    if factor_id == "detaljplaner" and v("detail_plans") is not None:
        return f"{int(v('detail_plans'))} zoning plans in the pipeline."
    if factor_id == "exploatering" and v("development_m2") is not None:
        return f"About {sv_num(v('development_m2') * 1000)} m² of development area planned."
    if factor_id == "infrastruktur" and v("infra_invest") is not None:
        return f"Public investment of about {sv_num(v('infra_invest'))} MSEK."
    if factor_id == "morgon" and v("flow_morning") is not None:
        return f"About {sv_num(v('flow_morning'))} passers-by per hour in the morning."
    if factor_id == "dag" and v("flow_midday") is not None:
        return f"About {sv_num(v('flow_midday'))} passers-by per hour at midday."
    if factor_id == "eftermiddag" and v("flow_afternoon") is not None:
        return f"About {sv_num(v('flow_afternoon'))} passers-by per hour after 2 pm."
    if factor_id == "gangtrafik" and v("foot_traffic") is not None:
        return f"About {sv_num(v('foot_traffic'))} passers-by per day in total."
    if factor_id == "lunch" and v("flow_midday") is not None:
        return (f"Lunch flow of about {sv_num(v('flow_midday'))} people/hour, "
                f"{sv_num(v('office_workers') or 0)} office workers within the radius.")
    if factor_id == "kvall" and v("flow_evening") is not None:
        return f"Evening flow of about {sv_num(v('flow_evening'))} people/hour."
    if factor_id == "bilbestand" and v("cars_per_1000") is not None:
        return (f"{int(v('cars_per_1000'))} cars per 1,000 residents, "
                f"average age {v('avg_car_age') or 0} years.")
    if factor_id == "upptagning" and v("pop_radius") is not None:
        return (f"{sv_num(v('pop_radius'))} people and "
                f"{sv_num(v('detached_homes') or 0)} detached-home households "
                f"in the catchment area.")
    if factor_id == "pendling" and v("commuter_flow") is not None:
        return f"About {sv_num(v('commuter_flow'))} commuters pass in the morning and evening."
    if factor_id == "naringsliv" and v("business_density") is not None:
        return f"{int(v('business_density'))} businesses per 1,000 residents."
    if factor_id == "djurunderlag" and v("pets_per_1000") is not None:
        return f"An estimated {int(v('pets_per_1000'))} pets per 1,000 residents."
    if factor_id == "logistiklage" and v("logistics_access") is not None:
        return (f"Logistics access {v('logistics_access')} of 10 "
                f"(proximity to highway, terminal and port).")
    if factor_id == "kostnadslage" and v("rent_index") is not None:
        idx = v("rent_index")
        rel = ("above" if idx > 105 else
               ("on par with" if idx >= 95 else "below"))
        return f"Rent level {rel} the national average (index {int(idx)})."
    if factor_id == "barnfamiljer" and v("families_share") is not None:
        return f"{v('families_share')}% families with children in the catchment area."
    if factor_id == "aldre" and v("share_65plus") is not None:
        return f"{v('share_65plus')}% of the population is 65+."

    return ""  # motorn fyller i generisk text om ingen mall matchar


def pattern_insights(vertical_id: str, extras: dict[str, Any]) -> list[str]:
    """Mönsterinsikter, t.ex. caféets 'Fantastiskt morgonflöde men svagt efter 14'."""
    out: list[str] = []
    flows = extras.get("flows")
    if vertical_id == "cafe" and flows:
        m, a = flows.get("morning", 0), flows.get("afternoon", 0)
        if m >= 350 and a < 0.45 * m:
            out.append("Strong morning flow – but very weak after 2 pm. "
                       "Consider a morning-focused concept or reduced "
                       "afternoon hours.")
        elif m >= 350:
            out.append("Even, strong flow throughout the day.")
    if vertical_id == "elektriker":
        c = extras.get("competitors", {})
        demand = extras.get("demand_units")
        if demand is not None:
            headroom = int(max(0, round(demand - c.get("effective", 0))))
            if headroom > 0:
                out.append(f"There is likely work here for another "
                           f"{headroom} electrician(s).")
            else:
                out.append("The market currently appears saturated.")
    return out
