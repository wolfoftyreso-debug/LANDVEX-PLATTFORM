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
    "monitors": "Bevakningsregler och deras fynd delas mellan kunder. "
                "En kund kan se att en annan bevakar en viss mätare.",
    "outcomes": "Utfallsloggen som kalibrerar överlevnadssannolikheter är "
                "gemensam. Den innehåller inga kundnamn, men väl vilka "
                "etableringar som prövats och hur det gick.",
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
    for t in ("monitors", "outcomes", "corrections", "signal_cache"):
        assert "tenant" not in cols[t], (
            f"{t} HAR nu en tenant-kolumn — bra, men ta då bort den ur "
            f"NOT_YET_ISOLATED så dokumentationen inte ljuger åt andra "
            f"hållet")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
