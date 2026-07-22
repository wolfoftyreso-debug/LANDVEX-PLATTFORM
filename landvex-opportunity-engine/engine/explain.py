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
        return f"{sv_num(v('pop_radius'))} personer inom {location.radius_minutes} minuter."
    if factor_id == "synlighet" and v("foot_traffic") is not None:
        return f"Lokalen passeras av cirka {sv_num(v('foot_traffic'))} personer per dag."
    if factor_id == "matchning" and v("target_match_pct") is not None:
        return f"{int(v('target_match_pct'))} % av förbipasserande tillhör målgruppen."
    if factor_id == "kopkraft" and v("income_index") is not None:
        idx = v("income_index")
        rel = "över" if idx > 102 else ("i nivå med" if idx >= 98 else "under")
        return f"Medelinkomst {rel} rikssnittet (index {int(idx)})."
    if factor_id == "tillvaxt" and v("pop_growth_pct") is not None:
        g = v("pop_growth_pct")
        riktning = "ökar" if g >= 0 else "minskar"
        return f"Befolkningen {riktning} med {str(abs(g)).replace('.', ',')} %."

    if factor_id == "konkurrens" and "competitors" in extras:
        c = extras["competitors"]
        huvud = (f"{c['count']} konkurrenter i området" if c["count"] != 1
                 else "1 konkurrent i området")
        delar = [huvud]
        if c["full_booked"]:
            delar.append(f"{c['full_booked']} "
                         f"{'fullbokad' if c['full_booked'] == 1 else 'fullbokade'}")
        if c["low_rated"]:
            delar.append(f"{c['low_rated']} med svaga recensioner")
        if c["premium"]:
            delar.append(f"{c['premium']} i premiumsegmentet")
        return ". ".join([delar[0]] + [d.capitalize() for d in delar[1:]]) + "."

    if factor_id in ("marknadsutrymme",) and v("provider_gap") is not None:
        gap = v("provider_gap")
        if gap >= 1.3:
            return "Efterfrågan överstiger dagens utbud – tydligt marknadsutrymme."
        if gap >= 0.95:
            return "Efterfrågan och utbud i balans."
        return "Utbudet överstiger sannolikt efterfrågan – mättad marknad."

    if factor_id == "byggaktivitet" and v("building_permits") is not None:
        return f"{sv_num(v('building_permits'))} bygglov beviljade senaste 12 månaderna."
    if factor_id == "fastighetsbestand" and v("detached_homes") is not None:
        return (f"{sv_num(v('detached_homes'))} villor/småhus i området, "
                f"snittålder cirka {int(v('avg_building_age') or 0)} år.")
    if factor_id == "elektrifiering" and v("ev_per_capita") is not None:
        return f"{int(v('ev_per_capita'))} elbilar per 1 000 invånare – växande laddbehov."
    if factor_id == "detaljplaner" and v("detail_plans") is not None:
        return f"{int(v('detail_plans'))} detaljplaner i pipeline."
    if factor_id == "exploatering" and v("development_m2") is not None:
        return f"Cirka {sv_num(v('development_m2') * 1000)} m² exploateringsyta planerad."
    if factor_id == "infrastruktur" and v("infra_invest") is not None:
        return f"Offentliga investeringar om cirka {sv_num(v('infra_invest'))} mnkr."
    if factor_id == "morgon" and v("flow_morning") is not None:
        return f"Cirka {sv_num(v('flow_morning'))} förbipasserande per timme på morgonen."
    if factor_id == "dag" and v("flow_midday") is not None:
        return f"Cirka {sv_num(v('flow_midday'))} förbipasserande per timme mitt på dagen."
    if factor_id == "eftermiddag" and v("flow_afternoon") is not None:
        return f"Cirka {sv_num(v('flow_afternoon'))} förbipasserande per timme efter kl 14."
    if factor_id == "gangtrafik" and v("foot_traffic") is not None:
        return f"Totalt cirka {sv_num(v('foot_traffic'))} förbipasserande per dag."
    if factor_id == "lunch" and v("flow_midday") is not None:
        return (f"Lunchflöde cirka {sv_num(v('flow_midday'))} personer/timme, "
                f"{sv_num(v('office_workers') or 0)} kontorsarbetare inom radien.")
    if factor_id == "kvall" and v("flow_evening") is not None:
        return f"Kvällsflöde cirka {sv_num(v('flow_evening'))} personer/timme."
    if factor_id == "barnfamiljer" and v("families_share") is not None:
        return f"{str(v('families_share')).replace('.', ',')} % barnfamiljer i upptagningsområdet."
    if factor_id == "aldre" and v("share_65plus") is not None:
        return f"{str(v('share_65plus')).replace('.', ',')} % av befolkningen är 65+."

    return ""  # motorn fyller i generisk text om ingen mall matchar


def pattern_insights(vertical_id: str, extras: dict[str, Any]) -> list[str]:
    """Mönsterinsikter, t.ex. caféets 'Fantastiskt morgonflöde men svagt efter 14'."""
    out: list[str] = []
    flows = extras.get("flows")
    if vertical_id == "cafe" and flows:
        m, a = flows.get("morning", 0), flows.get("afternoon", 0)
        if m >= 350 and a < 0.45 * m:
            out.append("Starkt morgonflöde – men mycket svagt efter klockan 14. "
                       "Överväg morgonfokuserat koncept eller reducerade eftermiddagstimmar.")
        elif m >= 350:
            out.append("Jämnt och starkt flöde över hela dagen.")
    if vertical_id == "elektriker":
        c = extras.get("competitors", {})
        demand = extras.get("demand_units")
        if demand is not None:
            headroom = int(max(0, round(demand - c.get("effective", 0))))
            if headroom > 0:
                out.append(f"Här finns sannolikt arbete för ytterligare "
                           f"{headroom} elektriker.")
            else:
                out.append("Marknaden bedöms i nuläget som mättad.")
    return out
