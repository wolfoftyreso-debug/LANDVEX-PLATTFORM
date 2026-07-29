"""Pushgeneratorn: leverans i valt format — och sanningen om leveransen.

Det farligaste en push kan göra är att SE levererad ut utan att vara
det, och det näst farligaste är att bli en väg runt paketet eller in i
vårt eget nät. Sviten prövar spärrarna före allt annat.

Kör: python3 -m tests.test_pushes
"""
from __future__ import annotations

from engine import pushes as P
from engine import scheduler as S


def test_a_preview_is_the_exact_payload_and_delivers_nothing():
    """Generatorns kärna: kunden ser exakt de bytes som skulle skickas —
    och ingenting skickas."""
    from engine.export import export

    fasit = export("imbalances", "csv", {"vertical": "frisor",
                                           "market": "se"}, tenant="t1")
    r = P.preview("imbalances", "csv", {"vertical": "frisor",
                                          "market": "se"}, tenant="t1")
    assert r["content"] == fasit["content"]
    assert r["delivered"] is False
    assert "Nothing was sent" in r["note_en"]
    assert r["media_type"].startswith("text/csv")
    assert r["bytes"] == len(r["content"].encode("utf-8"))


def test_a_refused_format_gives_the_export_engines_own_reason():
    try:
        P.preview("imbalances", "pdf", {}, tenant="t1")
    except P.PushRefused as e:
        assert "rendering library" in str(e)
    else:
        raise AssertionError("pdf skulle ha vägrats med exportens skäl")


def test_a_target_must_be_https_and_public():
    """En kunds webhook får inte bli vår väg in i vårt eget nät — och
    kontrollen säger själv vad den INTE ser (namn som pekar privat)."""
    P.validate_target("https://hooks.example.com/landvex")
    for adress in ("", "http://hooks.example.com/x",
                   "https://localhost/x", "https://127.0.0.1/x",
                   "https://10.0.0.5/x", "https://192.168.1.9/x",
                   "https://169.254.169.254/latest/meta-data",
                   "https://172.16.0.1/x", "https://172.31.9.9/x"):
        try:
            P.validate_target(adress)
        except P.PushRefused:
            continue
        raise AssertionError(f"{adress!r} borde ha vägrats")
    # 172.x utanför privatspannet är publikt och släpps igenom
    P.validate_target("https://172.15.0.1/x")
    P.validate_target("https://172.32.0.1/x")


def test_a_failed_post_never_looks_delivered():
    jobb = {"tenant": "t1", "params": {
        "dataset": "imbalances", "format": "csv",
        "dataset_params": {"vertical": "frisor", "market": "se"},
        "target_url": "https://hooks.example.com/x"}}

    def nere(url, body, headers, timeout):
        raise ConnectionRefusedError("connection refused")

    r = P.deliver(jobb, transport=nere)
    assert r["delivered"] is False
    assert "never got there" in r["why_en"]

    def fyrahundra(url, body, headers, timeout):
        return 400, b"bad request"

    r = P.deliver(jobb, transport=fyrahundra)
    assert r["delivered"] is False and r["status"] == 400
    assert "their word" in r["why_en"]


def test_a_delivered_post_carries_the_format_and_the_bytes():
    sedd = {}

    def mottagare(url, body, headers, timeout):
        sedd.update(url=url, body=body, headers=headers)
        return 200, b"ok"

    jobb = {"tenant": "t1", "params": {
        "dataset": "imbalances", "format": "ndjson",
        "dataset_params": {"vertical": "frisor", "market": "se"},
        "target_url": "https://hooks.example.com/x"}}
    r = P.deliver(jobb, transport=mottagare)
    assert r["delivered"] is True and r["status"] == 200
    assert sedd["headers"]["Content-Type"].startswith(
        "application/x-ndjson")
    assert len(sedd["body"]) == r["bytes"]
    # första raden är _landvex-proveniensen — förbehållen följer med
    assert b"_landvex" in sedd["body"].split(b"\n")[0]


def test_our_bug_in_the_transport_is_not_a_receiver_fault():
    jobb = {"tenant": "t1", "params": {
        "dataset": "imbalances", "format": "csv",
        "dataset_params": {"vertical": "frisor", "market": "se"},
        "target_url": "https://hooks.example.com/x"}}

    def trasig(url, body, headers, timeout):
        raise AttributeError("vår bugg")

    try:
        P.deliver(jobb, transport=trasig)
    except AttributeError:
        pass
    else:
        raise AssertionError("OUR_BUGS ska upp, inte kläs ut till nätfel")


def test_a_subscription_is_validated_when_created_not_at_3am():
    """Prenumerationen är ett schemalagt jobb — och scheduler.job vägrar
    redan vid skapandet när målet, datamängden eller formatet är fel."""
    ok = S.job("push-1", "push", tenant="t1", params={
        "dataset": "imbalances", "format": "csv",
        "target_url": "https://hooks.example.com/x"})
    assert ok["kind"] == "push"
    for fel in ({"dataset": "imbalances", "format": "csv"},
                {"dataset": "finns_inte", "format": "csv",
                 "target_url": "https://hooks.example.com/x"},
                {"dataset": "imbalances", "format": "pdf",
                 "target_url": "https://hooks.example.com/x"},
                {"dataset": "imbalances", "format": "csv",
                 "target_url": "https://192.168.0.1/x"}):
        try:
            S.job("push-x", "push", tenant="t1", params=fel)
        except S.ScheduleRefused:
            continue
        raise AssertionError(f"{fel} borde ha vägrats vid skapandet")


def test_the_push_job_kind_exists_and_reports_refusals_as_results():
    assert "push" in S.JOB_KINDS
    assert S.JOB_KINDS["push"]["capability"] == "core"
    # ett jobb vars mål hunnit bli ogiltigt EFTER skapandet: körningen
    # skriver vägran i registret i stället för att krascha tickern
    r = S.JOB_KINDS["push"]["run"](
        {"tenant": "t1", "params": {"dataset": "imbalances",
                                    "format": "csv", "target_url": ""}}, 0.0)
    assert r["delivered"] is False and "target_url" in r["why_en"]


def test_the_catalog_names_what_it_refuses_and_what_it_cannot():
    kat = P.catalog()
    assert any(f["id"] == "pdf" for f in kat["refused_formats"])
    assert "at-least-once" in kat["cannot_en"]
    assert kat["datasets"] and kat["formats"]
    assert "private" in kat["target_rules_en"]


def test_the_generator_is_reachable_without_buying_anything():
    from api.licensing import required_capability

    assert required_capability("/v1/pushes") == "core"
    assert required_capability("/v1/pushes/preview") == "core"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
