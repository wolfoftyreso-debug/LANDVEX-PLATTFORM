"""Tester för SVK/ENTSO-E-adaptern. Kör: python3 -m tests.test_svk"""
from __future__ import annotations

from engine.datasources.svk import SvkClient, balance_mw, stability_score


def test_stability_score():
    assert stability_score(50.0) == 100.0
    assert stability_score(49.9) == 90.0     # 0.1 Hz → −10
    assert stability_score(48.0) == 0.0      # klipps


def test_balance_mw():
    assert balance_mw(1000, 800, imp=50, exp=30) == 220.0


def test_not_connected():
    assert SvkClient(base_url="").connected is False
    assert SvkClient(base_url="").production_mix() is None


def test_normalize_psr_and_derived():
    raw = {"productionmix": [{"psrType": "B14", "quantity": 5000},
                             {"psrType": "B12", "quantity": 3000},
                             {"psrType": "B19", "quantity": 2000}],
           "frequency_hz": 49.98, "consumption_mw": 9000,
           "import_mw": 100, "export_mw": 200}
    out = SvkClient.normalize(raw)
    assert out["mix"]["nuclear"] == 5000 and out["mix"]["wind"] == 2000
    assert out["production_mw"] == 10000
    assert out["stability_score"] == stability_score(49.98)
    assert out["balance_mw"] == balance_mw(10000, 9000, 100, 200)


def test_production_mix_via_transport():
    c = SvkClient(base_url="https://svk",
                  transport=lambda u, t: '{"mix":{"hydro":4000},"frequency_hz":50.0}')
    out = c.production_mix()
    assert out["mix"]["hydro"] == 4000 and out["stability_score"] == 100.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
