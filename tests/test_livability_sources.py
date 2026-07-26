"""Tester för livsvillkorskällorna (Kolada + Eurostat) mot verkliga format.
Kör: python3 -m tests.test_livability_sources"""
from __future__ import annotations

import json

from engine.datasources import livability_sources as LS
from engine.datasources.adapters import LivabilitySource
from engine.models import Location
import tempfile

# Kolada v2 svarar så här på /data/kpi/{kpi}/municipality/{kommun}
KOLADA_REAL = {"count": 1, "values": [
    {"kpi": "N15428", "municipality": "0138", "period": 2023,
     "values": [{"count": 1, "gender": "T", "status": "", "value": 74.1},
                {"count": 1, "gender": "K", "status": "", "value": 77.0}]},
    {"kpi": "N15428", "municipality": "0138", "period": 2024,
     "values": [{"count": 1, "gender": "T", "status": "", "value": 76.4}]},
]}

EUROSTAT_REAL = {"class": "dataset", "value": {"0": 8.9},
                 "dimension": {"time": {"category": {"index": {"2023": 0,
                                                               "2024": 1}}}}}


def _tp(payload):
    def t(url, timeout):
        t.last_url = url
        return json.dumps(payload)
    t.last_url = None
    return t


def test_kolada_picks_the_total_from_the_latest_period():
    c = LS.KoladaLivability(base_url="http://k.example",
                            transport=_tp(KOLADA_REAL))
    got = c.value("education_outcomes", "0138")
    assert got["value"] == 76.4 and got["year"] == 2024     # senaste, gender T
    assert got["source"] == "kolada" and got["kpi"] == "N15428"
    assert "N15428" in c._transport.last_url and "0138" in c._transport.last_url


def test_transforms_are_explicit_and_crime_is_not_double_inverted():
    """crime_index normaliseras redan inverst i katalogen."""
    assert LS.KOLADA_SIGNALS["crime_index"]["transform"] == "direct"
    assert LS.KOLADA_SIGNALS["housing_affordability"]["transform"] == "pct_invert"
    assert LS.apply_transform(23, "pct_invert") == 77.0
    assert LS.apply_transform(116, "direct") == 116.0
    try:
        LS.apply_transform(1, "guess")
        raise AssertionError("okänd transform tilläts")
    except ValueError:
        pass
    # varje mappad signal ska finnas i signalkatalogen
    from engine.signals import CATALOG
    for sid in LS.KOLADA_SIGNALS:
        assert sid in CATALOG, sid


def test_no_answer_yields_no_value_never_a_guess():
    for payload in ({}, {"values": []},
                    {"values": [{"period": 2024, "values": [
                        {"gender": "K", "value": 5}]}]}):   # saknar total
        c = LS.KoladaLivability(base_url="http://k.example",
                                transport=_tp(payload))
        assert c.value("education_outcomes", "0138") is None

    def boom(url, timeout):
        raise OSError("blocked")
    assert LS.KoladaLivability(base_url="http://k.example",
                               transport=boom
                               ).value("education_outcomes", "0138") is None
    assert LS.KoladaLivability(base_url="").value("education_outcomes",
                                                  "0138") is None


def test_eurostat_reads_the_latest_and_flips_a_burden_into_affordability():
    c = LS.EurostatLivability(base_url="http://e.example",
                              transport=_tp(EUROSTAT_REAL))
    c.enabled = True
    got = c.value("housing_affordability", "SE")
    assert got["raw_value"] == 8.9 and got["value"] == 91.1   # 100 − 8.9
    assert got["year"] == "2024" and got["source"] == "eurostat"


def test_source_is_off_until_configured_and_falls_back_honestly():
    src = LivabilitySource()
    vals, extras = src.fetch(Location(59.24, 18.23), "generisk",
                             ["education_outcomes"])
    assert vals == {} and extras == {}          # ⇒ Resolvern går till mock


def test_source_returns_real_values_with_quality_by_confidence():
    class Fake:
        connected = True
        base_url = "http://k.example"

        def value(self, sid, kommun):
            return {"signal_id": sid, "value": 76.4, "raw_value": 76.4,
                    "transform": "direct", "year": 2024,
                    "kpi": LS.KOLADA_SIGNALS[sid]["kpi"], "label_en": "x",
                    "source": "kolada"}

    class Loc:
        def locate(self, lat, lon):          # samma namn som KommunLocator
            return ("0138", "Tyresö")

    src = LivabilitySource(client=Fake(), locator=Loc())
    vals, extras = src.fetch(Location(59.24, 18.23), "generisk",
                             ["education_outcomes", "social_trust"])
    assert vals["education_outcomes"].source == "livability"
    # bekräftat KPI väger tyngre än en kandidat
    assert vals["education_outcomes"].quality > vals["social_trust"].quality
    assert extras["livability_kpis"]["education_outcomes"]["kpi"] == "N15428"


def test_the_source_uses_the_locator_api_that_actually_exists():
    """Ett felstavat metodnamn tystades av fail-safe-except och gav mock."""
    from engine.datasources.scb import KommunLocator
    assert hasattr(KommunLocator, "locate")
    loc = KommunLocator()
    src = LivabilitySource(locator=loc)
    assert src._kommun(Location(59.24, 18.23)) == "0138"    # Tyresö


def test_unreachable_host_is_not_the_same_as_a_missing_kpi():
    """Blockerat nät får ALDRIG registreras som att ett KPI saknas.

    Första skarpa körningen gjorde precis det: proxyn svarade 403 på
    CONNECT, proben tolkade tystnaden som "KPI:t svarar inte" och skrev
    ned tre KPI:n som var bekräftade i skörden. Nätverksfel raderade
    verklig kunskap.
    """
    import socket
    import urllib.error

    blocked = urllib.error.URLError("Tunnel connection failed: 403 Forbidden")
    assert LS._classify(blocked) is True                 # onåbar
    assert LS._classify(socket.timeout("slow")) is True
    assert LS._classify(urllib.error.HTTPError(
        "u", 403, "Forbidden", None, None)) is True
    # men ett riktigt svar från servern är ett svar, även 404
    assert LS._classify(urllib.error.HTTPError(
        "u", 404, "Not Found", None, None)) is False
    assert LS._classify(ValueError("bad json")) is False

    def boom(url, timeout):
        raise blocked
    c = LS.KoladaLivability(base_url="http://k.example", transport=boom)
    ok, why = c.reachable()
    assert ok is False and "403" in why

    def fine(url, timeout):
        return json.dumps(KOLADA_REAL)
    ok, _ = LS.KoladaLivability(base_url="http://k.example",
                                transport=fine).reachable()
    assert ok is True


def test_defaults_stay_candidate_without_a_probe_result():
    """Verifiering ska aldrig följa med i repot.

    verified.json speglar vad som svarade på EN maskin. Committas den ser
    projektet ut att ha verifierade källor överallt. Utan filen ska
    kandidaterna förbli kandidater – den säkra defaulten.
    """
    import os
    assert not os.path.exists(LS.VERIFIED_PATH), (
        "verified.json ligger i trädet — den är miljöspecifik och ska "
        "vara ignorerad, annars påstås verifiering som inte gjorts")
    assert LS.load_verification("/nonexistent/probe.json") == {}
    for sid in ("social_trust", "housing_affordability", "care_supply"):
        assert LS.KOLADA_SIGNALS[sid]["verified"] is False, sid


def test_probe_result_overlays_and_can_downgrade(
        tmpdir=tempfile.gettempdir()):
    """Ett svar som uteblir ska sänka en signal, inte bara höja."""
    import copy
    saved = copy.deepcopy(LS.KOLADA_SIGNALS)
    try:
        n = LS.apply_verification({"kolada": {
            "care_supply": {"verified": True, "checked_at": "2026-01-01"},
            "education_outcomes": {"verified": False, "answered": False,
                                   "checked_at": "2026-01-01"}}})
        assert n == 2
        assert LS.KOLADA_SIGNALS["care_supply"]["verified"] is True
        # även ett tidigare bekräftat KPI kan falla om det slutar svara
        assert LS.KOLADA_SIGNALS["education_outcomes"]["verified"] is False
        assert LS.KOLADA_SIGNALS["education_outcomes"]["answered"] is False
    finally:
        LS.KOLADA_SIGNALS.clear()
        LS.KOLADA_SIGNALS.update(saved)


def test_catalog_separates_confirmed_from_candidate():
    c = LS.catalog()
    assert c["kolada"]["verified_count"] >= 3
    assert c["kolada"]["candidate_count"] >= 1
    assert "not been live-verified" in c["note_en"].lower() or \
           "NOT been live-verified" in c["note_en"]
    assert "livability_probe" in c["probe"]
    for s in c["eurostat"]["signals"]:
        assert s["verified"] is False       # inget påstås verifierat


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
