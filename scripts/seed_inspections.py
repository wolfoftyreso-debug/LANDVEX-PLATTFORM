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
    return {"tenant": TENANT, "assets": objekt, "routines": [rut],
            "checks": kontroller, "source": "mock",
            "customer_en": "Flag and flagpole supplier, Stockholm",
            "note_en": ("Simulated customer. The streets are real; the "
                        "objects, the checks and the verdicts are not. No "
                        "row here was ever performed by anyone."),
            "as_of": d0.isoformat()}


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
    return fix


def payload(today: str = "") -> dict:
    """Färdiga svar för demon — samma form som endpointerna svarar med.

    Byggs på fixturens egna listor i stället för via lagret: bygget ska
    inte kunna smitta en databas, och demon ska inte kunna råka visa
    riktiga kunddata.
    """
    from engine import inspections as I

    fix = flag_supplier(today)
    a, r, c = fix["assets"], fix["routines"], fix["checks"]
    return {
        "customer_en": fix["customer_en"], "note_en": fix["note_en"],
        "source": "mock", "as_of": fix["as_of"],
        "assets": {"assets": a, "source": "mock"},
        "routines": {"routines": r, "source": "mock"},
        "compliance": I.compliance(a, r, c, fix["as_of"]),
        "exceptions": I.exceptions(a, r, c, fix["as_of"]),
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
