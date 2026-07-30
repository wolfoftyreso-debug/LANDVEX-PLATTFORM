"""Tester för deploy/k8s/ — Kubernetes-spåret bredvid deploy/aws/.

Ingen PyYAML: CI kör utan pip install (se .github/workflows/ci.yml), så
manifesten tolkas med samma regex-disciplin som Dockerfile och
task-definition.json redan tolkas med i tests/test_deploy.py. Ett
manifest som byter form utan att detta test märker det är precis det
felet vi vill fånga.

Kör: python3 -m tests.test_k8s
"""
from __future__ import annotations

import json
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_K8S = _ROOT / "deploy" / "k8s"


def _read(name: str) -> str:
    return (_K8S / name).read_text(encoding="utf-8")


def _configmap_data() -> dict[str, str]:
    text = _read("configmap.yaml")
    block = text.split("data:", 1)[1]
    return dict(re.findall(r'^\s{2}([A-Z][A-Za-z0-9_]*):\s*"(.*)"\s*$',
                            block, re.M))


def _secret_keys() -> list[str]:
    text = _read("secret.example.yaml")
    block = text.split("stringData:", 1)[1]
    return re.findall(r'^\s{2}([A-Z][A-Za-z0-9_]*):\s*""\s*$', block, re.M)


def _deployment() -> str:
    return _read("deployment.yaml")


def _taskdef() -> dict:
    return json.loads((_ROOT / "deploy" / "aws" / "task-definition.json")
                      .read_text(encoding="utf-8"))


def _ecs_container() -> dict:
    return _taskdef()["containerDefinitions"][0]


# ── ConfigMap ────────────────────────────────────────────────────────────
def test_every_configmap_variable_is_read_by_the_code():
    """Samma regel som ECS-sidan: en dokumenterad variabel som inte finns
    i registret är en gissning, inte en konfiguration."""
    from engine.deployment import ENVIRONMENT
    okanda = sorted(set(_configmap_data()) - set(ENVIRONMENT))
    assert not okanda, f"sätts i ConfigMap men läses aldrig av koden: {okanda}"


def test_no_secret_is_placed_in_the_configmap():
    from engine.deployment import ENVIRONMENT
    data = _configmap_data()
    lackta = sorted(k for k in data if ENVIRONMENT[k]["secret"])
    assert not lackta, f"hemligheter i klartext i ConfigMap: {lackta}"


def test_preflight_is_strict_here_too():
    assert _configmap_data()["LANDVEX_PREFLIGHT"] == "strict"


def test_persistence_is_off_because_two_replicas_cannot_share_sqlite():
    """Två repliker × standardkonkurrens är fler skrivare än en SQLite-fil
    tål — samma logik som ECS-sidans LANDVEX_DB=off, se docs/aws.md §3."""
    data = _configmap_data()
    assert data["LANDVEX_DB"] == "off"
    assert "LANDVEX_PG_DSN" not in data, \
        "LANDVEX_PG_DSN är hemlig — hör hemma i secret.example.yaml"


def test_the_replica_count_matches_the_declared_env_var():
    """LANDVEX_REPLICAS är den enda siffran som dupliceras utanför sin
    källa (samma anmärkning som docs/aws.md gör om desired-count)."""
    m = re.search(r"^\s*replicas:\s*(\d+)\s*$", _deployment(), re.M)
    assert m, "deployment.yaml saknar spec.replicas"
    assert int(m.group(1)) == int(_configmap_data()["LANDVEX_REPLICAS"])


# ── Secret ───────────────────────────────────────────────────────────────
def test_the_secret_template_only_names_variables_marked_secret():
    from engine.deployment import ENVIRONMENT
    icke_hemliga = sorted(k for k in _secret_keys()
                          if not ENVIRONMENT[k]["secret"])
    assert not icke_hemliga, (
        f"secret.example.yaml namnger icke-hemliga variabler: {icke_hemliga}")


def test_the_secret_template_carries_the_variables_the_pg_path_needs():
    keys = set(_secret_keys())
    assert {"LANDVEX_API_KEYS", "LANDVEX_JWT_SECRET",
            "LANDVEX_PG_DSN"} <= keys


def test_the_secret_example_never_carries_a_real_looking_value():
    """En mall med ett värde som ser äkta ut är en läcka som väntar på att
    checkas in på riktigt."""
    text = _read("secret.example.yaml")
    stringdata = text.split("stringData:", 1)[1]
    for rad in re.findall(r'^\s{2}[A-Z][A-Za-z0-9_]*:\s*(.*)$',
                          stringdata, re.M):
        assert rad == '""', f"secret.example.yaml har ett värde: {rad!r}"


def test_the_secret_template_matches_the_ecs_secret_list():
    """Samma fem variabler ska korsa in som hemlighet oavsett vilken väg
    som kör tjänsten — annars beskriver de två spåren olika tjänster."""
    ecs = {s["name"] for s in _ecs_container()["secrets"]}
    assert set(_secret_keys()) == ecs


# ── Deployment: hälsa, tajmning, icke-root ───────────────────────────────
def test_the_container_port_matches_the_configmap_and_the_image():
    dep = _deployment()
    m = re.search(r"containerPort:\s*(\d+)", dep)
    assert m, "deployment.yaml saknar containerPort"
    port = m.group(1)
    assert port == _configmap_data()["LANDVEX_PORT"]
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert f"EXPOSE {port}" in dockerfile


def test_the_probes_match_the_ecs_health_check():
    """Två spår, en hälsodefinition. En probe som tystnar fångas annars
    bara av vem som råkar driftsätta den vägen först."""
    hc = _ecs_container()["healthCheck"]
    dep = _deployment()
    probar = re.findall(
        r"initialDelaySeconds:\s*(\d+)\s*\n\s*periodSeconds:\s*(\d+)\s*\n"
        r"\s*timeoutSeconds:\s*(\d+)\s*\n\s*failureThreshold:\s*(\d+)", dep)
    assert len(probar) == 2, "förväntade readiness- och livenessProbe"
    for delay, period, timeout, retries in probar:
        assert int(delay) == hc["startPeriod"]
        assert int(period) == hc["interval"]
        assert int(timeout) == hc["timeout"]
        assert int(retries) == hc["retries"]
    assert "path: /health" in dep


def test_the_grace_period_outlives_the_gunicorn_timeout():
    """Samma anmärkning som ECS-sidans stopTimeout-test: en pod som dödas
    innan gunicorn hunnit svara skär av pågående anrop i stället för att
    avsluta dem."""
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    m = re.search(r"--timeout (\d+)", dockerfile)
    assert m, "gunicorn-timeouten står inte i Dockerfile"
    grace = re.search(r"terminationGracePeriodSeconds:\s*(\d+)", _deployment())
    assert grace, "deployment.yaml saknar terminationGracePeriodSeconds"
    assert int(grace.group(1)) > int(m.group(1))
    # Och ECS ska hålla samma tal, så en driftsättare inte möter olika
    # avslutstider beroende på vilket spår som råkar köra.
    assert int(grace.group(1)) == _ecs_container()["stopTimeout"]


def test_the_container_runs_as_the_same_non_root_uid_as_the_image():
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    m = re.search(r"--uid (\d+)", dockerfile)
    assert m, "Dockerfile saknar --uid"
    uid = m.group(1)
    dep = _deployment()
    assert f"runAsUser: {uid}" in dep
    assert "runAsNonRoot: true" in dep


def test_the_image_repository_matches_the_ecr_repo_the_report_asked_for():
    """infra/infrastruktur-inventering-2026-07-30.md §6: ECR-repot heter
    landvex/opportunity-engine. Ett annat namn i manifestet registrerar
    sig aldrig mot det repot CI faktiskt skapar."""
    assert "landvex/opportunity-engine" in _deployment()
    kustomization = _read("kustomization.yaml")
    assert "landvex/opportunity-engine" in kustomization


# ── Namespace-konsekvens ──────────────────────────────────────────────────
def test_every_manifest_agrees_on_the_namespace():
    filer = ("namespace.yaml", "configmap.yaml", "secret.example.yaml",
            "deployment.yaml", "service.yaml", "ingress.yaml")
    for fil in filer:
        text = _read(fil)
        if fil == "namespace.yaml":
            assert re.search(r"^\s*name:\s*landvex\s*$", text, re.M), fil
            continue
        assert re.search(r"^\s*namespace:\s*landvex\s*$", text, re.M), \
            f"{fil} saknar eller har fel namespace"


def test_the_ingress_host_is_the_domain_the_report_says_does_not_exist_yet():
    """Ett påstående som redan är sant i manifestet men falskt i AWS —
    det är precis vad checklistan i docs/k8s.md ska stänga, inte något
    det här testet ska tro är klart."""
    ingress = _read("ingress.yaml")
    assert "opportunity.landvex.com" in ingress
    assert "${ACM_CERTIFICATE_ARN}" in ingress, (
        "certifikat-ARN:et ska vara ett fyll-i-placeholder tills "
        "infra/infrastruktur-inventering-2026-07-30.md gap #5 är stängt")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
