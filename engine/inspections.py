"""Återkommande kontroller av fysiska tillgångar — och beviset efteråt.

Plattformen kunde svara på frågor om platser men inte hålla reda på
OBJEKT över tid. En flaggleverantör som sköter flaggstänger i stora delar
av Stockholm och en kommun som ska kontrollera livbojar på badplatser har
samma behov, och det fanns ingen del av det: inget register över kundens
egna objekt, inget sätt att säga "det här ska ses över varje vecka",
ingen förfalloräkning, och inget efterlevnadsregister att visa en nämnd
eller en försäkringsgivare efter att något hänt.

Modulen är medvetet generisk. En flaggstång, en livboj, en badstege, en
skylt och en laddstolpe är samma sak för motorn: ett objekt med en plats
som någon ansvarar för och som ska ses till med jämna mellanrum.

Tre begrepp:

    ASSET     ett objekt kunden äger, med koordinat och ägare
    ROUTINE   vad som ska kontrolleras, hur ofta, av vem, och vad som
              räknas som godkänt
    CHECK     en utförd eller förfallen kontroll, med sitt utfall

## Kadensen gissar inte

`every_days`, valfri `weekday`, valfri `season` täcker veckovis
flaggkontroll och badplatssäsong. Allt annat — "efter storm", "vid
behov", "två gånger per säsong" — **avvisas med namngivet skäl** i
stället för att tolkas. En rutin som tyst blir något annat än vad någon
skrev är farligare än en rutin som vägras: den som skrev den tror att
kontrollen sker.

Samma sak för `weekday` med ett `every_days` som inte är delbart med 7.
"Var tredje dag, på tisdagar" går inte att uppfylla, och att välja åt
någon vilken av de två som ska vinna vore att hitta på en rutin.

## Mediet lagras aldrig här

En fältbild på en badplats eller en gata innehåller människor. Landvex
lagrar **domen och referensen** — uppdrags-id och en pekare — aldrig
bilden. Den stannar hos quiXzoom, som har samtycket och kedjan. Ett test
faller om ett fält som ser ut att bära media läggs till i en CHECK.

## Domen säger vad den vilar på

En kontroll är EN observation från EN källa. Den kan konstatera att
livbojen saknades den dagen; den kan inte säga att den varit borta i tre
veckor, och den säger ingenting om varför. Det står i `cannot_en` och
följer med i svaret.

Rent stdlib. Rena funktioner, injicerbar `today` för testbarhet.
"""
from __future__ import annotations

import datetime as _dt

VERDICTS = ("pass", "fail", "missing", "unclear")
STATUSES = ("never_checked", "ok", "due_soon", "overdue", "failed",
            "out_of_season")

# Hur nära förfall något ska vara för att kallas "snart". En vecka är
# den horisont en driftplanering faktiskt arbetar i.
DUE_SOON_DAYS = 7


class RoutineError(ValueError):
    """En rutin som inte går att uppfylla får inte skapas."""


# ── Datum ───────────────────────────────────────────────────────────────
def _datum(v: object) -> _dt.date:
    if isinstance(v, _dt.date):
        return v
    if isinstance(v, str) and v:
        return _dt.date.fromisoformat(v[:10])
    raise ValueError(f"kan inte tolka datumet {v!r}")


def _idag(today: object = "") -> _dt.date:
    return _datum(today) if today else _dt.date.today()


def _sasong(sasong: tuple[str, str] | None, d: _dt.date) -> bool:
    """Ligger datumet inom säsongen? Hanterar vintersäsong som vänder
    över årsskiftet (11-01 → 03-31)."""
    if not sasong:
        return True
    fran, till = sasong
    md = f"{d.month:02d}-{d.day:02d}"
    if fran <= till:
        return fran <= md <= till
    return md >= fran or md <= till          # vänder vid årsskiftet


def _in_i_sasongen(sasong: tuple[str, str] | None, d: _dt.date) -> _dt.date:
    """Flytta fram till säsongens början om datumet hamnat utanför."""
    if _sasong(sasong, d):
        return d
    for _ in range(400):                     # högst ett år framåt
        d += _dt.timedelta(days=1)
        if _sasong(sasong, d):
            return d
    raise RoutineError("säsongen går aldrig in — kontrollera från/till")


# ── Rutinen ─────────────────────────────────────────────────────────────
def audience(pool: str = "open", zoomer_ids: tuple[str, ...] = (),
             label_en: str = "") -> dict:
    """Vem som får ta uppdraget — öppna poolen eller namngivna zoomers.

    En hyrbilsflotta fotas av de egna anställda; en butiks skyltning av
    butikspersonalen. Båda är quiXzoom-konton som vilka andra som helst
    — skillnaden är att uppdraget RIKTAS till dem i stället för att
    läggas i öppna poolen. Riktningen är data på rutinen, och
    beställningen översätter den; ingenting i domslut, bevis eller
    lagring ändras av vem som höll kameran.

    `zoomer_ids` är quiXzoom-kontoreferenser och ingenting annat: namn
    och e-post vägras, för personerna och deras samtycke bor hos
    quiXzoom — Landvex lagrar referensen, aldrig människan.
    """
    if pool not in ("open", "named"):
        raise RoutineError(f"audience.pool är 'open' eller 'named', "
                           f"fick {pool!r}")
    if pool == "named" and not zoomer_ids:
        raise RoutineError(
            "en riktad publik utan zoomer_ids är en tom pool: uppdraget "
            "hade beställts och aldrig kunnat tas av någon")
    if pool == "open" and zoomer_ids:
        raise RoutineError(
            "zoomer_ids med pool='open' är tvetydigt — riktat eller "
            "öppet? Välj 'named' om listan ska gälla.")
    for zid in zoomer_ids:
        if "@" in zid or " " in zid or not zid.strip():
            raise RoutineError(
                f"zoomer_ids ska vara quiXzoom-kontoreferenser, inte "
                f"namn eller e-post ({zid!r}): personen och samtycket "
                f"bor hos quiXzoom, Landvex lagrar referensen")
    return {"pool": pool, "zoomer_ids": tuple(zoomer_ids),
            "label_en": label_en}


def routine(id: str, label_en: str, applies_to: str, every_days: int, *,
            checks: tuple[str, ...] = (), weekday: int | None = None,
            season: tuple[str, str] | None = None,
            owners: dict | None = None, expected: dict | None = None,
            audience_: dict | None = None,
            tenant: str = "") -> dict:
    """Skapa en rutin, eller vägra med ett skäl som går att åtgärda."""
    if every_days < 1:
        raise RoutineError("every_days måste vara minst 1")
    if weekday is not None:
        if not 0 <= weekday <= 6:
            raise RoutineError("weekday är 0–6 (måndag–söndag)")
        if every_days % 7:
            raise RoutineError(
                f"every_days={every_days} går inte ihop med en fast "
                f"veckodag — 'var {every_days}:e dag, på en bestämd "
                f"veckodag' går inte att uppfylla. Välj ett intervall "
                f"delbart med 7, eller ta bort veckodagen.")
    if season:
        for m in season:
            if not (isinstance(m, str) and len(m) == 5 and m[2] == "-"):
                raise RoutineError(
                    f"säsongen anges som MM-DD, fick {m!r}")
    if not checks:
        raise RoutineError(
            "en rutin utan `checks` säger inte vad som räknas som "
            "godkänt, och då går ingen dom att motivera")
    # Publiken valideras även när den kommer som rå dict (ur ett API-
    # anrop): en rutin med trasig riktning ska falla när den skapas,
    # inte när beställningen misslyckas månader senare.
    pub = (audience(**audience_) if audience_ is not None
           else audience())
    return {
        "id": id, "tenant": tenant, "label_en": label_en,
        "applies_to": applies_to, "every_days": every_days,
        "weekday": weekday, "season": season, "checks": tuple(checks),
        "owners": dict(owners or {}), "expected": dict(expected or {}),
        "audience": pub,
    }


def next_due(rut: dict, last_checked: object = "",
             today: object = "") -> str:
    """Nästa förfallodag som ISO-datum.

    Utan tidigare kontroll förfaller den idag: ett objekt som aldrig
    setts till är inte "aktuellt i väntan på första gången".
    """
    idag = _idag(today)
    if not last_checked:
        d = idag
    else:
        d = _datum(last_checked) + _dt.timedelta(days=rut["every_days"])
    if rut.get("weekday") is not None:
        # Kliv framåt till rätt veckodag. every_days är delbart med 7,
        # så intervallet bevaras.
        while d.weekday() != rut["weekday"]:
            d += _dt.timedelta(days=1)
    return _in_i_sasongen(rut.get("season"), d).isoformat()


# ── Status ──────────────────────────────────────────────────────────────
def status(rut: dict, checks: list[dict], today: object = "") -> dict:
    """Var står det här objektet just nu?

    `checks` är kontrollerna för ETT objekt, i valfri ordning.
    """
    idag = _idag(today)
    utforda = sorted((c for c in checks if c.get("performed_at")),
                     key=lambda c: c["performed_at"])
    senaste = utforda[-1] if utforda else None

    if senaste and senaste.get("verdict") in ("fail", "missing"):
        return {"status": "failed", "days_overdue": 0,
                "last_checked": senaste["performed_at"],
                "last_verdict": senaste["verdict"],
                "next_due": next_due(rut, senaste["performed_at"], idag),
                "why_en": f"Last check came back {senaste['verdict']}. "
                          f"That outranks the schedule: a failed object "
                          f"is not made current by being checked on time."}

    forfaller = next_due(rut, senaste["performed_at"] if senaste else "",
                         idag)
    dag = _datum(forfaller)
    if not _sasong(rut.get("season"), idag):
        lage, sen = "out_of_season", 0
    elif dag < idag:
        lage, sen = "overdue", (idag - dag).days
    elif (dag - idag).days <= DUE_SOON_DAYS:
        lage, sen = "due_soon", 0
    else:
        lage, sen = "ok", 0
    if senaste is None and lage != "out_of_season":
        lage = "never_checked"

    return {"status": lage, "days_overdue": sen,
            "last_checked": senaste["performed_at"] if senaste else None,
            "last_verdict": senaste.get("verdict") if senaste else None,
            "next_due": forfaller,
            "why_en": _varfor(lage, sen, rut)}


def _varfor(lage: str, sen: int, rut: dict) -> str:
    return {
        "never_checked": "No check on record. An object that has never "
                         "been seen is not current — it is unknown.",
        "ok": f"Checked within the {rut['every_days']}-day interval.",
        "due_soon": f"Falls due within {DUE_SOON_DAYS} days.",
        "overdue": f"{sen} day(s) past due. The interval says how often "
                   f"someone decided this must be seen; the number is "
                   f"how far past that decision it now is.",
        "failed": "Last check did not pass.",
        "out_of_season": "Outside the season this routine applies to. "
                         "Not overdue — not required right now.",
    }[lage]


# ── Kontrollen ──────────────────────────────────────────────────────────
def record(asset_id: str, routine_id: str, verdict: str, *,
           performed_at: str = "", mission_id: str = "",
           evidence_ref: str = "", observed_by: str = "",
           note_en: str = "", tenant: str = "") -> dict:
    """Registrera ett utfall. Kräver bevis för allt utom `unclear`.

    En godkänd kontroll utan bevis är ett påstående, inte en kontroll —
    och det är just den sortens post som blir värdelös i efterhand, när
    någon frågar vad den vilade på.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"okänt utfall {verdict!r}; välj bland {VERDICTS}")
    if verdict != "unclear" and not (mission_id or evidence_ref):
        raise ValueError(
            f"utfallet {verdict!r} kräver bevis (mission_id eller "
            f"evidence_ref). En dom utan bevis går inte att försvara i "
            f"efterhand, och det är i efterhand den behövs.")
    return {
        "asset_id": asset_id, "routine_id": routine_id, "tenant": tenant,
        "verdict": verdict,
        "performed_at": performed_at or _dt.date.today().isoformat(),
        # Mediet lagras ALDRIG här — bara pekaren. Bilden stannar hos
        # quiXzoom, som har samtycket och insamlingskedjan.
        "mission_id": mission_id, "evidence_ref": evidence_ref,
        "observed_by": observed_by, "note_en": note_en,
        "basis_en": ("One observation from one source at one moment. It "
                     "can establish what was there that day; it cannot "
                     "say for how long, and it does not say why."),
    }


# ── Leveranserna ────────────────────────────────────────────────────────
def compliance(assets: list[dict], routines: list[dict],
               checks: list[dict], today: object = "") -> dict:
    """Efterlevnadsregistret — varje objekt, senast sett, nästa förfall."""
    per_rutin = {r["id"]: r for r in routines}
    rader = []
    for a in assets:
        rut = _rutin_for(a, routines, per_rutin)
        if rut is None:
            rader.append({"asset": a, "status": "no_routine",
                          "why_en": "No routine covers this object. It is "
                                    "in the register and nobody has said "
                                    "how often it should be seen."})
            continue
        egna = [c for c in checks if c.get("asset_id") == a["id"]
                and c.get("routine_id") == rut["id"]]
        rader.append({"asset": a, "routine_id": rut["id"],
                      **status(rut, egna, today)})

    raknare: dict[str, int] = {}
    for r in rader:
        raknare[r["status"]] = raknare.get(r["status"], 0) + 1
    aktuella = raknare.get("ok", 0) + raknare.get("due_soon", 0)
    return {
        "rows": rader, "count": len(rader), "by_status": raknare,
        "current": aktuella,
        "share_current": round(aktuella / len(rader), 4) if rader else None,
        "as_of": _idag(today).isoformat(),
        "means_en": ("What can be shown afterwards: every object, when it "
                     "was last seen, when it falls due next, and what the "
                     "last verdict was."),
        "cannot_en": ("A register of checks is not a guarantee of "
                      "condition. It says an object passed when it was "
                      "looked at — not that it is intact now."),
    }


def exceptions(assets: list[dict], routines: list[dict],
               checks: list[dict], today: object = "") -> dict:
    """Avvikelseflödet — bara det som kräver någon."""
    allt = compliance(assets, routines, checks, today)
    avvik = [r for r in allt["rows"]
             if r["status"] in ("overdue", "failed", "never_checked",
                                "no_routine")]
    avvik.sort(key=lambda r: (r["status"] != "failed",
                              -int(r.get("days_overdue") or 0)))
    return {
        "exceptions": avvik, "count": len(avvik),
        "of_total": allt["count"], "as_of": allt["as_of"],
        "quiet_en": ("Nothing needs anyone today. A quiet exception feed "
                     "is a real result — a feed that always finds "
                     "something is a feed that invents."),
    }


def _rutin_for(a: dict, routines: list[dict],
               per_id: dict) -> dict | None:
    for r in routines:
        mal = r.get("applies_to")
        if mal == a.get("kind") or mal == a.get("id"):
            return r
        if isinstance(mal, (list, tuple)) and a.get("id") in mal:
            return r
    return None


# ── Lager: store om det finns, annars processminne ──────────────────────
# Samma mönster som engine/monitors.py. Motorn äger inte affärslogiken —
# API-lagret gör det, och API-lagret SKA skicka med tenant. Utan tenant
# returneras allt, vilket är rätt för en batchkörning och fel för ett
# kundanrop; den skillnaden bevakas av tests/test_tenancy.py.
import threading as _threading

_LOCK = _threading.Lock()
_ASSETS: list[dict] = []
_ROUTINES: list[dict] = []
_CHECKS: list[dict] = []
_STORE = None


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def _spara(lista: list[dict], rec: dict, metod: str, nyckel: str) -> str:
    if _STORE is not None and getattr(_STORE, metod, None):
        return getattr(_STORE, metod)(rec)
    with _LOCK:
        for i, r in enumerate(lista):
            if r.get(nyckel) == rec.get(nyckel):
                lista[i] = rec
                return rec[nyckel]
        lista.append(rec)
    return rec[nyckel]


def save_asset(rec: dict) -> str:
    return _spara(_ASSETS, rec, "save_asset", "id")


def save_routine(rec: dict) -> str:
    return _spara(_ROUTINES, rec, "save_routine", "id")


def save_check(rec: dict) -> str:
    with _LOCK:
        _CHECKS.append(rec)
    if _STORE is not None and getattr(_STORE, "save_check", None):
        _STORE.save_check(rec)
    return f"{rec['asset_id']}:{rec['performed_at']}"


def _las(lista: list[dict], metod: str, tenant: str | None) -> list[dict]:
    rader = (getattr(_STORE, metod)() if _STORE is not None
             and getattr(_STORE, metod, None) else list(lista))
    if tenant is None:
        return rader
    return [r for r in rader if r.get("tenant", "") == tenant]


def all_assets(tenant: str | None = None) -> list[dict]:
    return _las(_ASSETS, "all_assets", tenant)


def all_routines(tenant: str | None = None) -> list[dict]:
    return _las(_ROUTINES, "all_routines", tenant)


def all_checks(tenant: str | None = None) -> list[dict]:
    return _las(_CHECKS, "all_checks", tenant)


def reset() -> None:
    """Endast för tester."""
    with _LOCK:
        _ASSETS.clear()
        _ROUTINES.clear()
        _CHECKS.clear()


def asset(id: str, kind: str, *, label_en: str = "", lat: float | None = None,
          lon: float | None = None, address: str = "",
          installed_at: str = "", tenant: str = "") -> dict:
    """Ett objekt kunden äger."""
    if not id or not kind:
        raise ValueError("ett objekt behöver både id och kind")
    return {"id": id, "kind": kind, "label_en": label_en or id,
            "lat": lat, "lon": lon, "address": address,
            "installed_at": installed_at, "tenant": tenant}


def report(tenant: str, today: object = "") -> dict:
    """Efterlevnadsregistret för EN kund."""
    return compliance(all_assets(tenant), all_routines(tenant),
                      all_checks(tenant), today)


def exception_feed(tenant: str, today: object = "") -> dict:
    return exceptions(all_assets(tenant), all_routines(tenant),
                      all_checks(tenant), today)


def due_now(tenant: str, today: object = "") -> dict:
    """Vad som förfaller — underlaget för en beställningskörning."""
    rap = report(tenant, today)
    rader = [r for r in rap["rows"]
             if r["status"] in ("overdue", "due_soon", "never_checked")]
    return {"due": rader, "count": len(rader), "as_of": rap["as_of"],
            "means_en": ("What a dispatch run would order today. "
                         "'never_checked' is included: an object nobody "
                         "has looked at is not waiting, it is unknown.")}


def accountability_card(rut: dict, *, committed_at: str = "",
                        tenant: str = "") -> dict:
    """Ansvarskortet för EN rutin — samma register som alla andra beslut.

    Ett intervall är ett beslut någon fattade: att det här objektet ska
    ses så här ofta. Utan ett namn på det beslutet blir en missad kontroll
    ingen mans sak, och det är precis då den blir farlig. Kortet läggs
    därför i `engine/accountability.py` — ingen egen ansvarsmodell här.

    Vägrar med de tre rollnamnen i klartext i stället för att skapa ett
    beslut utan ägare.
    """
    from engine.accountability import commit
    from engine.claims import OWNER_ROLES

    ag = dict(rut.get("owners") or {})
    saknas = [r for r in OWNER_ROLES if not str(ag.get(r, "")).strip()]
    if saknas:
        raise RoutineError(
            f"rutinen {rut['id']!r} saknar ansvariga {saknas} — en rutin "
            f"utan ägare gör en missad kontroll till ingens sak. Rollerna "
            f"är {list(OWNER_ROLES)}: den som beslutar, den som utför och "
            f"den som svarar för att den blev gjord.")
    forv = dict(rut.get("expected") or {})
    for f in ("metric", "direction", "target"):
        if f not in forv:
            raise RoutineError(
                f"rutinen {rut['id']!r} saknar {f!r} i `expected`. Ett "
                f"mätbart förväntat utfall är vad kortet stäms av mot; "
                f"utan det går rutinen inte att infria eller missa.")
    return commit(
        f"Inspection routine {rut['id']}: {rut.get('label_en') or rut['id']}"
        f" — every {rut['every_days']} day(s)",
        ag, forv, horizon_months=12, committed_at=committed_at,
        tenant=tenant or rut.get("tenant", ""))


def route_exceptions(tenant: str, today: object = "",
                     subs: list[dict] | None = None,
                     decisions: list[dict] | None = None) -> dict:
    """Skicka avvikelserna till den som ska agera på dem.

    Avvikelseflödet är en lista tills någon får den. Routingen ligger i
    `engine/inbox.py` — samma väg som allt annat som ska nå en människa,
    så att en missad kontroll rankas mot resten av det som hänt och inte
    i en egen liten kö som ingen öppnar.

    **`subs` är obligatoriskt i praktiken.** Prenumerationerna i
    `engine/inbox.py` bär ingen tenant. Skulle den här funktionen falla
    tillbaka på `inbox.subscriptions()` skickades en kunds avvikelser —
    med adress och objekt — till alla andras prenumeranter. Den vägrar i
    stället, med skälet utskrivet.
    """
    from engine import inbox

    flode = exception_feed(tenant, today)
    handelser = [inbox.from_inspection_exception(r)
                 for r in flode["exceptions"]]
    if subs is None:
        return {
            "routed": [], "routed_count": 0, "as_of": flode["as_of"],
            "exceptions_count": len(handelser),
            "refusal_en": (
                "No subscriptions were passed, and subscriptions in "
                "engine/inbox.py carry no tenant. Routing to every "
                "subscriber would hand one customer's addresses and "
                "objects to another's inbox, so nothing was routed. Pass "
                "this customer's own subscriptions explicitly."),
        }
    ut = inbox.route(handelser, subs, decisions=decisions)
    return {**ut, "routed_count": len(handelser), "as_of": flode["as_of"],
            "means_en": ("Exceptions ranked against everything else the "
                         "recipient has at stake. An overdue lifebuoy is "
                         "not a notification; it is something someone "
                         "owns.")}


def catalog() -> dict:
    return {
        "verdicts": list(VERDICTS), "statuses": list(STATUSES),
        "due_soon_days": DUE_SOON_DAYS,
        "principle_en": (
            "A routine that quietly becomes something other than what "
            "someone wrote is more dangerous than one that is refused: "
            "whoever wrote it believes the check is happening. Cadences "
            "that cannot be expressed exactly are rejected with a named "
            "reason instead of interpreted."),
        "privacy_en": (
            "A field photograph of a beach or a street contains people. "
            "The verdict and a reference are stored here; the image stays "
            "with quiXzoom, which holds the consent and the chain."),
    }
