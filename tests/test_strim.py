"""Tester för STRIM-entitetsgrafen. Kör: python3 -m tests.test_strim"""
from __future__ import annotations

from engine import strim as S


def _ent(**kw):
    base = dict(entity_type="term", slug="opportunity-score",
                name_en="Opportunity Score",
                definition="A 0-100 score describing modelled success probability.",
                sources=["LANDVEX methodology v1"])
    base.update(kw)
    return S.build_entity(**base)


def test_build_and_schema_org_mapping():
    e = _ent(entity_type="statistic", slug="pop-growth")
    assert e["schema_org"] == "Dataset" and e["version"] == 1
    assert e["checksum"]


def test_slug_must_be_canonical():
    try:
        _ent(slug="Not Valid")
        raise AssertionError()
    except ValueError:
        pass


def test_requires_source():
    try:
        _ent(sources=[])
        raise AssertionError()
    except ValueError:
        pass


def test_neutral_language_enforced():
    try:
        _ent(definition="This is the best score and you should use it")
        raise AssertionError()
    except ValueError:
        pass


def test_revise_versions_and_slug_immutable():
    v1 = _ent()
    v2 = S.revise(v1, definition="A 0-100 modelled score with confidence.")
    assert v2["version"] == 2 and v2["previous_version"] == v1["checksum"]
    try:
        S.revise(v1, canonical_slug="new-slug")
        raise AssertionError()
    except ValueError:
        pass


def test_relations_typed():
    e = _ent()
    S.add_relation(e, "related_to", "risk-score")
    assert e["relations"][0]["target"] == "risk-score"
    try:
        S.add_relation(e, "bogus", "x")
        raise AssertionError()
    except ValueError:
        pass


def test_jsonld_and_cite():
    e = _ent()
    ld = S.to_jsonld(e)
    assert ld["@type"] == "DefinedTerm" and ld["@context"] == "https://schema.org"
    assert "strim:term:opportunity-score" in S.cite(e, "text")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
