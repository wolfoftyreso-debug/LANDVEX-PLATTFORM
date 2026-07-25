"""Tester för anslutnings-cockpit. Kör: python3 -m tests.test_sources"""
from __future__ import annotations

import os

from api.sources import sources_status


def test_lists_all_adapters():
    s = sources_status()
    ids = {x["id"] for x in s["sources"]}
    assert {"scb", "kolada", "svk", "permits", "places", "aamos"} <= ids
    assert s["total"] == len(s["sources"])


def test_env_var_flips_state_to_live():
    os.environ.pop("LANDVEX_KOLADA_URL", None)
    before = next(x for x in sources_status()["sources"] if x["id"] == "kolada")
    assert before["state"] == "mock"
    os.environ["LANDVEX_KOLADA_URL"] = "https://api.kolada.se/v2"
    try:
        after = next(x for x in sources_status()["sources"] if x["id"] == "kolada")
        assert after["state"] == "live"
        assert "LANDVEX_KOLADA_URL" in after["activate_with"]
    finally:
        os.environ.pop("LANDVEX_KOLADA_URL", None)


def test_each_source_names_its_env_and_official_source():
    for x in sources_status()["sources"]:
        assert x["activate_with"] and x["official_source"] and x["provides"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
