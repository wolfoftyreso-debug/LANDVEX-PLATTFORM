"""Vem ser vad — och vad är ÄNNU inte isolerat.

Fyndet: plattformen autentiserade tenant, loggade tenant i varje
revisionsrad, och kastade den sedan innan lagret rördes. Bara
`usage_meter` bar en tenant-kolumn. Bevisat mot en körande server med två
API-nycklar: "Konkurrent AB" kunde lista OCH läsa "Tyresö kommuns"
profil, och se kommunens ansvarskort med beslutsfattarnas namn.

Det här är den sortens fel som inte syns i en demo och inte i ett
enhetstest — bara när två kunder finns i samma databas.

Testerna nedan gör två saker, och den andra är minst lika viktig:

  1. Låser fast det som NU är isolerat.
  2. Skriver ned det som ÄNNU INTE är det. En halvt isolerad plattform
     som tros vara helt isolerad är farligare än en som ingen litar på.
     Luckan står här i klartext så den inte kan glömmas bort, och testet
     faller när någon stänger den — då ska listan uppdateras, inte
     luckan upptäckas på nytt.

Kör: python3 -m tests.test_tenancy
"""
from __future__ import annotations

import inspect

from engine import accountability
from engine.storage.sqlite import SqliteStore

_A = "tyreso-kommun"
_B = "konkurrent-ab"


def _store() -> SqliteStore:
    return SqliteStore(":memory:")


# ── Det som är isolerat ──────────────────────────────────────────────────
def test_profiles_and_reports_are_scoped_to_the_owning_tenant():
    s = _store()
    pid = s.save_profile({"name": "HEMLIG plan", "vertical_id": "frisor"},
                         created_at=1000.0, tenant=_A)
    rid = s.save_report({"vertical_id": "frisor", "opportunity_score": 50.0,
                         "data_coverage": 0.5,
                         "location": {"lat": 59.3, "lon": 18.1,
                                      "address": "x"}},
                        created_at=1000.0, tenant=_A)
    # Ägaren ser sitt.
    assert [r["profile_id"] for r in s.list_profiles(tenant=_A)] == [pid]
    assert [r["report_id"] for r in s.list_reports(tenant=_A)] == [rid]
    # Grannen ser ingenting — inte ens med id:t i handen.
    assert s.list_profiles(tenant=_B) == []
    assert s.list_reports(tenant=_B) == []
    assert s.get_profile(pid, tenant=_B) is None
    assert s.get_report(rid, tenant=_B) is None


def test_the_accountability_ledger_is_scoped_too():
    """Läckte namnen på beslutsfattare, antal beslut och infriandegrad."""
    accountability.set_store(None)          # processminne, deterministiskt
    accountability._DECISIONS.clear()
    common = {"expected": {"metric": "kostnad", "direction": "decrease",
                           "target": 8.0}}
    accountability.commit("HEMLIGT: lägg ner enheten",
                          {"formellt": "Kommundirektören", "operativt": "HR",
                           "uppfoljning": "Revision"},
                          tenant=_A, **common)
    accountability.commit("Konkurrentens beslut",
                          {"formellt": "VD", "operativt": "Drift",
                           "uppfoljning": "Styrelse"},
                          tenant=_B, **common)

    a = accountability.ledger(tenant=_A)
    b = accountability.ledger(tenant=_B)
    assert [r["owner"] for r in a["ledger"]] == ["Kommundirektören"]
    assert [r["owner"] for r in b["ledger"]] == ["VD"]
    # Ingen tenant alls ⇒ ingen filtrering. Motorn äger inte affärslogiken,
    # API-lagret gör det — och API-lagret SKA skicka med tenant.
    assert len(accountability.ledger()["ledger"]) == 2


def test_tenant_cannot_be_forgotten_on_the_store():
    """Ett argument med default är en läcka som väntar."""
    for name in ("save_report", "get_report", "list_reports",
                 "save_profile", "get_profile", "list_profiles"):
        p = inspect.signature(getattr(SqliteStore, name)).parameters["tenant"]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY, name
        assert p.default is inspect.Parameter.empty, name


def test_both_api_layers_pass_a_tenant_to_every_scoped_call():
    """Isolering i lagret hjälper inte om ett anropsställe glömmer den.
    Läses statiskt, så testet fångar ett NYTT anrop någon lägger till."""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parent.parent / "api"
    scoped = ("save_report", "get_report", "list_reports",
              "save_profile", "get_profile", "list_profiles")
    missing = []
    for f in ("main.py", "dev_server.py"):
        src = (root / f).read_text(encoding="utf-8")
        for m in re.finditer(r"STORE\.(" + "|".join(scoped) + r")\(", src):
            i, depth = m.end(), 1
            while depth and i < len(src):
                depth += (src[i] == "(") - (src[i] == ")")
                i += 1
            if "tenant=" not in src[m.start():i]:
                missing.append(f"{f}: {src[m.start():m.end()]}…")
    assert not missing, "anrop utan tenant:\n  " + "\n  ".join(missing)


# ── Det som ÄNNU INTE är isolerat ────────────────────────────────────────
# Varje rad är en känd lucka, inte en glömd. Stänger någon en av dem ska
# raden tas bort här — testet nedan säger till.
NOT_YET_ISOLATED: dict[str, str] = {
    "outcomes": "Utfallsloggen delas MED FLIT. Kalibreringen blir bättre "
                "ju fler utfall den sett, och det enda som lämnar motorn "
                "är aggregat (Brier, hinkar, n) — råposterna nås inte av "
                "någon endpoint. Se testet nedan som håller fast vid "
                "båda halvorna av det påståendet.",
    "corrections": "Medborgarrättelser är AVSIKTLIGT gemensamma — de är "
                   "en allmänning. Står här för att valet ska vara "
                   "uttalat, inte antaget.",
    "signal_cache": "Cache av offentliga källdata. Avsiktligt gemensam: "
                    "samma SCB-siffra är samma siffra för alla, och en "
                    "delad cache är hela poängen.",
}


def test_the_remaining_gaps_are_written_down_not_forgotten():
    """En halvt isolerad plattform som tros vara helt isolerad är farligare
    än en ingen litar på."""
    assert NOT_YET_ISOLATED, "luckorna får inte tömmas utan att stängas"
    for area, why in NOT_YET_ISOLATED.items():
        assert len(why) > 40, f"{area} saknar en riktig förklaring"


def test_the_store_still_lacks_a_tenant_column_where_we_say_it_does():
    """Påståendet ovan måste stämma med koden. Blir en tabell isolerad
    utan att listan uppdateras faller det här — och tvärtom."""
    s = _store()
    cols = {t: {r[1] for r in s._conn.execute(f"PRAGMA table_info({t})")}
            for t in ("reports", "profiles", "monitors", "outcomes",
                      "corrections", "signal_cache")}
    for t in ("reports", "profiles"):
        assert "tenant" in cols[t], f"{t} skulle vara isolerad"
    for t in ("outcomes", "corrections", "signal_cache"):
        assert "tenant" not in cols[t], (
            f"{t} HAR nu en tenant-kolumn — bra, men ta då bort den ur "
            f"NOT_YET_ISOLATED så dokumentationen inte ljuger åt andra "
            f"hållet")




def test_monitors_are_scoped_to_the_tenant_that_defined_them():
    """`all_monitors()` gav alla kunders regler, och /v1/monitors/run
    matade exakt den listan till evalueringen: en kund körde cron och fick
    svar på en annans bevakningar — vilken mätare de vakar på, vilken
    tröskel de satt och vem hos dem som är ansvarig."""
    from engine import monitors
    monitors.set_store(None)
    monitors.reset()
    a = monitors.define("kostnad", "tyreso", "threshold", "Kommundirektören",
                        params={"level": 10, "direction": "above"},
                        label="HEMLIG kommunbevakning", tenant=_A)
    b = monitors.define("intakt", "sthlm", "threshold", "VD",
                        params={"level": 5, "direction": "above"},
                        label="konkurrentens", tenant=_B)
    assert [m["label"] for m in monitors.all_monitors(_A)] == \
        ["HEMLIG kommunbevakning"]
    assert [m["label"] for m in monitors.all_monitors(_B)] == ["konkurrentens"]
    # Att KÄNNA id:t ska inte räcka.
    assert monitors.get_monitor(a["id"], _B) is None
    assert monitors.get_monitor(a["id"], _A) is not None
    assert monitors.get_monitor(b["id"], _A) is None


def test_the_outcome_log_shares_learning_but_never_a_record():
    """Utfallsloggen delas med flit — kalibreringen blir bättre av fler
    utfall. Men det som LÄMNAR motorn måste vara aggregat. Det här testet
    håller fast vid båda halvorna: delad inlärning, inga läckta poster."""
    import json

    from engine import outcomes
    outcomes.set_store(None)
    outcomes.reset()
    rec = outcomes.log_outcome(
        {"lat": 59.31, "lon": 18.07, "address": "HEMLIG adress 12"},
        "frisor", 70.0, True)
    outcomes.record(rec)
    rapport = json.dumps(outcomes.calibration(), ensure_ascii=False)
    assert "HEMLIG" not in rapport, "kalibreringen läckte en råpost"
    assert "adress" not in rapport

    # Och ingen endpoint får börja servera råposterna.
    import pathlib
    import re
    api = pathlib.Path(__file__).resolve().parent.parent / "api"
    for f in ("main.py", "dev_server.py"):
        src = (api / f).read_text(encoding="utf-8")
        assert not re.search(r"\ball_records\b|\ball_outcomes\b", src), (
            f"{f} exponerar utfallens råposter — då är det inte längre "
            f"ett delat aggregat utan en läcka")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
