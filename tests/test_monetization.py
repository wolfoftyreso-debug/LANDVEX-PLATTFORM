"""Tester för komplexitetsbudget + månadsfönster.
Kör: python3 -m tests.test_monetization"""
from __future__ import annotations

from api import licensing as L


def test_complexity_limits_per_plan():
    assert L.complexity_limit("free") == 100
    assert L.complexity_limit("pro") == 1000
    assert L.complexity_limit("growth") == 1000   # alias för pro
    assert L.complexity_limit("enterprise") == 0   # obegränsat


def test_check_complexity():
    assert L.check_complexity("free", 100) is True
    assert L.check_complexity("free", 101) is False
    assert L.check_complexity("pro", 900) is True
    assert L.check_complexity("enterprise", 999999) is True


def test_usage_window_key_deterministic():
    assert L.usage_window_key("t1", "ask", "2026-07") == "t1:ask:2026-07"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
