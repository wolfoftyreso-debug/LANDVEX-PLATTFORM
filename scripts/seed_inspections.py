"""Demofixtur: flaggleverantören i Stockholm.

    python3 -m scripts.seed_inspections            # visar registret
    python3 -m scripts.seed_inspections --seed     # skriver till lagret

Första riktiga kunden för kontrollmodulen sköter flaggor och flaggstänger
åt fastighetsägare, kommuner och företag i stora delar av Stockholm.
Åtagandet är enkelt att formulera och svårt att bevisa: flaggan ska vara
uppe, hel och på rätt plats — varje vecka, på varje adress.

Fixturen är **simulerad och märkt som simulerad** (`source="mock"` följer
med i nyttolasten). Adresserna är riktiga gator; objekten, kontrollerna
och utfallen är påhittade. Ingen av raderna ska någonsin läsas som en
utförd kontroll.

Utfallen är blandade med flit, för det är blandningen som visar vad
modulen är till för:

  * några stänger är kontrollerade och aktuella,
  * en är **underkänd** (trasig lina) — den ska ligga överst i
    avvikelseflödet oavsett när nästa kontroll infaller,
  * några är **aldrig kontrollerade**, vilket inte är samma sak som
    godkänt och inte får se ut som det,
  * en ligger **försenad** med ett räknat antal dagar.

Rent stdlib.
"""
from __future__ import annotations

import datetime as _dt
import sys

TENANT = "flaggab"
ROUTINE_ID = "flaggkontroll_vecka"

# Riktiga gator i Stockholm; koordinaterna är avrundade och objekten
# påhittade. Sista fältet är hur många dagar sedan objektet senast
# kontrollerades — None betyder att det aldrig har kontrollerats.
_STANGER: tuple[tuple[str, str, str, float, float, int | None, str], ...] = (
    ("fp-hamn-01", "Flagpole · Stadshuskajen", "Hantverkargatan 1",
     59.3275, 18.0543, 3, "pass"),
    ("fp-torg-02", "Flagpole · Norrmalmstorg", "Norrmalmstorg 4",
     59.3325, 18.0729, 5, "pass"),
    ("fp-skol-03", "Flagpole · Södra Latin", "Skaraborgsgatan 14",
     59.3175, 18.0713, 19, "fail"),
    ("fp-park-04", "Flagpole · Humlegården", "Sturegatan 32",
     59.3396, 18.0770, None, ""),
    ("fp-kaj-05", "Flagpole · Norr Mälarstrand", "Norr Mälarstrand 76",
     59.3268, 18.0313, None, ""),
    ("fp-idr-06", "Flagpole · Zinkensdamms IP", "Ringvägen 12",
     59.3159, 18.0463, 11, "pass"),
    ("fp-kont-07", "Flagpole · Kungsholmstorg", "Kungsholmstorg 6",
     59.3283, 18.0431, None, ""),
    ("fp-bad-08", "Flagpole · Smedsuddsbadet", "Smedsuddsvägen 2",
     59.3243, 18.0173, 30, "pass"),
)


def _idag(today: str = "") -> _dt.date:
    return _dt.date.fromisoformat(today) if today else _dt.date.today()


def flag_supplier(today: str = "") -> dict:
    """Objekt, rutin och kontroller för demokunden. Ren data."""
    from engine import inspections as I

    d0 = _idag(today)
    rut = I.routine(
        ROUTINE_ID, "Weekly flag check", "flagpole", 7,
        checks=["present", "intact", "raised", "undamaged halyard"],
        weekday=1,                      # tisdagar
        # Rollnamnen är engine/claims.OWNER_ROLES, inte egna: kortet ska
        # kunna gå rakt in i ansvarsregistret utan översättning.
        owners={"formellt": "Contract manager, Flaggservice AB",
                "operativt": "quiXzoom field contributor (verified)",
                "uppfoljning": "Operations manager, Flaggservice AB"},
        # Mätbart, inte en avsiktsförklaring: andelen objekt som är
        # aktuella ska nå 1,0. Det är samma tal som registret räknar.
        expected={"metric": "share_current", "direction": "reach",
                  "target": 1.0},
        tenant=TENANT)

    # Den riktade varianten: skyltningen fotas av BUTIKSPERSONALEN, inte
    # öppna poolen — samma quiXzoom-konton som alla andra, men uppdraget
    # går till namngivna referenser. (Samma mekanism bär "egna anställda
    # fotar hyrbilarna": publiken är rutinens data, inte en egen modul.)
    rut_skylt = I.routine(
        "skyltkontroll-vecka", "Weekly signage check", "storefront", 7,
        checks=["campaign visible", "price tags current", "window clean"],
        owners={"formellt": "Store manager, Flaggservice AB",
                "operativt": "Store staff (named quiXzoom accounts)",
                "uppfoljning": "Operations manager, Flaggservice AB"},
        expected={"metric": "share_current", "direction": "reach",
                  "target": 1.0},
        audience_={"pool": "named",
                   "zoomer_ids": ("qz-staff-001", "qz-staff-002"),
                   "label_en": "Own store staff"},
        tenant=TENANT)

    # Två infrastrukturobjekt med observationer i OLIKA färskhetslägen —
    # färskhetstavlan ska visa current/ageing/stale/never direkt, inte
    # en tom yta som kräver att någon först observerar.
    infra_objekt, infra_obs = _infrastruktur(d0)

    objekt, kontroller = [], []
    for aid, label, adress, lat, lon, sedan, utfall in _STANGER:
        objekt.append(I.asset(aid, "flagpole", label_en=label, lat=lat,
                              lon=lon, address=adress,
                              installed_at="2021-04-06", tenant=TENANT))
        if sedan is None:
            continue
        kontroller.append(I.record(
            aid, ROUTINE_ID, utfall,
            performed_at=(d0 - _dt.timedelta(days=sedan)).isoformat(),
            mission_id=f"qz-mock-{aid}",
            observed_by="quixzoom-contributor-mock",
            note_en=("Halyard worn through; flag could not be raised."
                     if utfall == "fail" else ""),
            tenant=TENANT))
    return {"tenant": TENANT, "assets": objekt + infra_objekt,
            "routines": [rut, rut_skylt],
            "checks": kontroller, "observations": infra_obs,
            "source": "mock",
            "customer_en": "Flag and flagpole supplier, Stockholm",
            "note_en": ("Simulated customer. The streets are real; the "
                        "objects, the checks and the verdicts are not. No "
                        "row here was ever performed by anyone."),
            "as_of": d0.isoformat()}


def _infrastruktur(d0) -> tuple[list[dict], list[dict]]:
    """Cykelparkering + bilparkering med observationer i olika åldrar.

    Åldrarna är valda så att tavlan visar HELA färskhetsskalan:
    beläggning 5 min gammal (current), snö/hinder 3 h (ageing),
    lediga platser 4 h (stale → last_known), och några fält aldrig
    sedda (never). Ingen rad är verklig, precis som resten av fixturen.
    """
    import time as _t

    from engine import infrastructure as INF
    from engine import inspections as I

    nu = _t.time()
    objekt = [
        I.asset("infra-cykel-city", "bike_parking",
                label_en="Bicycle parking, Sergelgatan",
                lat=59.3326, lon=18.0649,
                address="Sergelgatan 11", tenant=TENANT),
        I.asset("infra-garage-nord", "car_parking",
                label_en="Garage Nord, Norra Bantorget",
                lat=59.3346, lon=18.0527,
                address="Norra Bantorget 2", tenant=TENANT),
    ]
    obs = [
        INF.observe("infra-cykel-city", "bike_parking",
                    {"occupancy": 0.85, "misparked": 3},
                    mission_id="qz-mock-cykel-1", tenant=TENANT,
                    observed_at=nu - 5 * 60),
        INF.observe("infra-cykel-city", "bike_parking",
                    {"rack_damage": "acceptable", "litter": "good"},
                    mission_id="qz-mock-cykel-2", tenant=TENANT,
                    observed_at=nu - 30 * 3600),
        INF.observe("infra-garage-nord", "car_parking",
                    {"free_spaces": 14, "occupancy": 0.82},
                    mission_id="qz-mock-garage-1", tenant=TENANT,
                    observed_at=nu - 4 * 3600),
        INF.observe("infra-garage-nord", "car_parking",
                    {"snow_or_obstruction": "good",
                     "payment_machine_works": True},
                    mission_id="qz-mock-garage-2", tenant=TENANT,
                    observed_at=nu - 3 * 3600),
    ]
    return objekt, obs


def seed(today: str = "") -> dict:
    """Skriv fixturen till det konfigurerade lagret."""
    from engine import inspections as I

    fix = flag_supplier(today)
    for r in fix["routines"]:
        I.save_routine(r)
    for a in fix["assets"]:
        I.save_asset(a)
    for c in fix["checks"]:
        I.save_check(c)
    for o in fix["observations"]:
        I.save_observation(o)
    return fix


def payload(today: str = "") -> dict:
    """Färdiga svar för demon — samma form som endpointerna svarar med.

    Byggs på fixturens egna listor i stället för via lagret: bygget ska
    inte kunna smitta en databas, och demon ska inte kunna råka visa
    riktiga kunddata.
    """
    from engine import inspections as I

    from engine import infrastructure as INF

    fix = flag_supplier(today)
    a, r, c = fix["assets"], fix["routines"], fix["checks"]
    obs = fix["observations"]
    infra = [x for x in a if x.get("kind") in INF.OBJECT_TYPES]
    return {
        "customer_en": fix["customer_en"], "note_en": fix["note_en"],
        "source": "mock", "as_of": fix["as_of"],
        "assets": {"assets": a, "source": "mock"},
        "routines": {"routines": r, "source": "mock"},
        "compliance": I.compliance(a, r, c, fix["as_of"]),
        "exceptions": I.exceptions(a, r, c, fix["as_of"]),
        # Färskhetstavlan: status/förfall FRYSTA vid bygget — åldrarna i
        # svaren är byggögonblickets, och det är ärligt: demon påstår
        # aldrig att den mäter nu.
        "infra_catalog": INF.catalog(),
        "infra_status": {x["id"]: INF.status(x["id"], x["kind"], obs)
                         for x in infra},
        "infra_due": INF.due(infra, obs),
        # SLA-exemplet för demons standardval (240 min / 7 dygn) — andra
        # kombinationer hänvisar ärligt till live-API:t.
        "infra_sla": INF.sla_report(infra, obs, promised_minutes=240.0,
                                    window_hours=168.0),
    }


def main(argv: list[str]) -> int:
    fix = seed(argv[1] if len(argv) > 1 and not argv[1].startswith("--")
               else "") if "--seed" in argv else flag_supplier()
    from engine import inspections as I

    rap = I.compliance(fix["assets"], fix["routines"], fix["checks"],
                       fix["as_of"])
    print(f"{fix['customer_en']} · {fix['source']} · {fix['as_of']}")
    print(f"  {rap['count']} objekt · {rap['current']} aktuella "
          f"({round(rap['share_current'] * 100)} %) · {rap['by_status']}")
    for rad in rap["rows"]:
        print(f"  {rad['asset']['id']:<12} {rad['status']:<14} "
              f"nästa {rad['next_due']}  {rad['asset']['address']}")
    if "--seed" in argv:
        print("skrivet till lagret")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
