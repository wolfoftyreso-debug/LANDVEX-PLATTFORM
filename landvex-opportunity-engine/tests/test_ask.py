"""Tester för Fråga Landvex (NL-tolk + svar). Körs utan pytest:
python3 -m tests.test_ask"""
from __future__ import annotations

from engine.ask import ask, parse


# ── Tolkning ─────────────────────────────────────────────────────────

def test_parse_mojligheter():
    q = parse("Vilka är de fem största affärsmöjligheterna i Örebro just nu?")
    assert q.intent == "mojligheter_kommun"
    assert q.kommun[1] == "Örebro"
    assert q.top_n == 5


def test_parse_bristyrken_med_horisont():
    q = parse("Vilka yrkesgrupper saknas mest i Umeå de kommande fem åren?")
    assert q.intent == "bristyrken_kommun"
    assert q.kommun[1] == "Umeå"
    assert q.target_year == 2031            # BASE_YEAR 2026 + 5


def test_parse_nationell_brist():
    q = parse("Var i Sverige är behovet av elektriker störst?")
    assert q.intent == "nationell_brist"
    assert q.occupation_id == "elektriker"


def test_parse_vertikal_synonymer_och_genitiv():
    q = parse("Var ska jag öppna kafé?")
    assert q.intent == "basta_lage_vertikal" and q.vertical_id == "cafe"
    q2 = parse("Största affärsmöjligheterna i Kalmars centrum?")
    assert q2.kommun[1] == "Kalmar"
    q3 = parse("Var behövs det flest rörmokare?")
    assert q3.occupation_id == "vvs_montor"


def test_parse_elektriker_kontext():
    # "elektriker" är både yrke och bransch – kontexten ska avgöra.
    assert parse("Var är bristen på elektriker störst?").intent == "nationell_brist"
    assert parse("Ska jag starta elektrikerfirma i Borås?"
                 ).vertical_id == "elektriker"


def test_parse_risk():
    q = parse("Hur riskabelt är det att starta gym i Solna?")
    assert q.intent == "riskprofil"
    assert q.vertical_id == "gym" and q.kommun[1] == "Solna"


def test_parse_okand_kommun_och_hjalp():
    q = parse("Vilka yrken saknas i Hyltes kommun?")
    assert q.intent == "okand_kommun" and q.unmatched_kommun == "Hylte"
    assert parse("Hur är vädret?").intent == "hjalp"


# ── Svar ─────────────────────────────────────────────────────────────

def test_ask_mojligheter_rows():
    res = ask("Vilka är de tre största affärsmöjligheterna i Örebro?")
    assert res["intent"] == "mojligheter_kommun"
    assert len(res["rader"]) == 3
    scores = [r["score"] for r in res["rader"]]
    assert scores == sorted(scores, reverse=True)
    d = res["rader"][0]["detalj"]
    assert d["risk_band"] and d["faktorer"] and "ekonomi_schablon" in d
    assert res["caveats_sv"] and res["forslag_sv"]


def test_ask_bristyrken_rows():
    res = ask("Vilka yrkesgrupper saknas mest i Umeå de kommande fem åren?")
    assert res["intent"] == "bristyrken_kommun"
    assert res["rader"]
    d = res["rader"][0]["detalj"]
    for key in ("behov_nu", "behov_prognos", "intervall", "konfidens",
                "pensionsavgangar", "medellon_tkr_manad",
                "automationsrisk_schablon", "drivare", "antaganden"):
        assert key in d, key
    assert res["rader"][0]["trend"] in ("stigande", "stabil", "minskande")
    assert res["rader"][0]["efterfragan"] in ("mattad", "vaxande", "hog", "extrem")


def test_ask_nationell_med_karta():
    res = ask("Var i Sverige är behovet av sjuksköterskor störst?")
    assert res["intent"] == "nationell_brist"
    assert res["karta"]["typ"] == "efterfragan"
    assert len(res["karta"]["kommuner"]) == 40
    assert all(k["efterfragan"] in ("mattad", "vaxande", "hog", "extrem")
               for k in res["karta"]["kommuner"])


def test_ask_hotspots_med_karta():
    res = ask("Var ska jag öppna café?")
    assert res["intent"] == "basta_lage_vertikal"
    assert res["karta"]["typ"] == "heatmap"
    assert res["rader"][0]["detalj"]["ekonomi_schablon"]


def test_ask_deterministic_och_tomt():
    f = "Vilka är de största affärsmöjligheterna i Gävle?"
    assert ask(f) == ask(f)
    res = ask("")
    assert res["intent"] == "hjalp" and res["forslag_sv"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
