"""Pushar — kunden genererar sina egna leveranser i valt mediaformat.

"API-generatorn" är inte en kodgenerator: den är tre val och ett schema.
Kunden väljer DATAMÄNGD (exportmotorns katalog), FORMAT (CSV, NDJSON,
GeoJSON — med förbehållen inbakade I filen) och MÅL (en webhook), och
sparar valet som ett schemalagt jobb. En pushprenumeration ÄR ett jobb
av typen `push`: `scheduled_jobs` bär redan tenant, params, cron-lucka
och claim-mekaniken som hindrar dubbelleverans — en egen tabell hade
varit en andra sanning om samma sak.

Doktrinen, ärvd rakt av:

* **Formatet är exportmotorns.** PDF/XLSX/Parquet vägras DÄR, med skäl
  som står i katalogen — pushen lägger bara leveransen ovanpå och kan
  inte trolla fram format som kärnan inte bär.
* **Utan mål levereras ingenting**, och ingenting rapporteras levererat.
  Ett påhittat leveranskvitto ser ut som en fungerande integration ända
  tills kunden frågar var filerna är.
* **Målet valideras när prenumerationen skapas**: https, och inga
  loopback-/privatadresser — en kunds webhook får inte bli vår väg in i
  vårt eget nät (SSRF). Vad kontrollen INTE kan: ett publikt namn som
  pekar privat i DNS ses inte härifrån; egress-policyn är det verkliga
  staketet, det här är första grinden.
* **Leveransresultatet skrivs på jobbet** — delivered/failed med skäl
  och HTTP-status. Ett misslyckat POST får aldrig se ut som ett
  levererat, och tystnad är inte ett resultat.

Rent stdlib.
"""
from __future__ import annotations

import urllib.request
from typing import Callable

from .datasources.faults import OUR_BUGS, unreachable
from .export import FORMATS, REFUSED_FORMATS, ExportRefused, export
from .export import catalog as export_catalog


class PushRefused(ValueError):
    """Pushen gick inte att göra eller skapa, och varför."""


# ── Målvalidering: första grinden mot SSRF ─────────────────────────────
_PRIVATA_PREFIX = ("127.", "10.", "192.168.", "169.254.", "0.")
_PRIVATA_NAMN = ("localhost", "metadata.google.internal")


def validate_target(url: str) -> str:
    """Godkänn en webhook-adress eller vägra med skälet.

    Körs när prenumerationen SKAPAS — ett mål som vägras månader senare,
    i en obevakad nattkörning, är ett fel ingen ser.
    """
    from urllib.parse import urlsplit

    if not url:
        raise PushRefused(
            "a push without a target_url delivers nowhere. Nothing is "
            "sent and nothing will be reported as sent — set the "
            "webhook address the receiving system listens on.")
    delar = urlsplit(url)
    if delar.scheme != "https":
        raise PushRefused(
            f"target_url must be https, got {delar.scheme!r}: the "
            f"payload carries one customer's own rows and travels the "
            f"open internet.")
    vard = (delar.hostname or "").lower()
    if vard in _PRIVATA_NAMN or vard.startswith(_PRIVATA_PREFIX) \
            or vard.startswith("172.") and vard.split(".")[1].isdigit() \
            and 16 <= int(vard.split(".")[1]) <= 31:
        raise PushRefused(
            f"target_url points at a private or loopback address "
            f"({vard}): a customer webhook must not become a path into "
            f"our own network. A public name that RESOLVES privately is "
            f"not caught here — the egress policy is the real fence.")
    return url


def validate_subscription(params: dict, *, tenant: str | None = None) -> None:
    """Hela prenumerationen prövas när den SKAPAS — mål, datamängd och
    format. Ett fel som först syns i en obevakad nattkörning är ett fel
    ingen ser.

    Målet är ANTINGEN en rå target_url ELLER en koppling (params
    ["connection"] = provider ur kundens kryp-in): då hämtas adress och
    autentisering ur kopplingslagret vid varje leverans — hemligheten
    bor kvar där den maskeras, aldrig i jobbets params."""
    p = params or {}
    if p.get("connection") and p.get("target_url"):
        raise PushRefused(
            "give target_url OR connection, not both — two targets for "
            "one delivery is an ambiguity someone discovers at 03:00")
    if p.get("connection"):
        if tenant is not None:
            from engine.connections import (ConnectionRefused,
                                            get_connection,
                                            target_url_of)
            try:
                target_url_of(get_connection(p["connection"],
                                             tenant=tenant))
            except ConnectionRefused as e:
                raise PushRefused(str(e)) from e
    else:
        validate_target(p.get("target_url", ""))
    ds = (params or {}).get("dataset", "")
    kanda = {d["id"] for d in export_catalog()["datasets"]}
    if ds not in kanda:
        raise PushRefused(f"unknown dataset {ds!r}. Available: "
                          f"{', '.join(sorted(kanda))}")
    fmt = (params or {}).get("format", "csv")
    if fmt in REFUSED_FORMATS:
        raise PushRefused(f"{fmt}: {REFUSED_FORMATS[fmt]}")
    if fmt not in FORMATS:
        raise PushRefused(f"unknown format {fmt!r}. Available: "
                          f"{', '.join(FORMATS)}")


# ── Bygga innehållet (generatorns förhandsvisning) ─────────────────────
def preview(dataset_id: str, format: str = "csv",
            params: dict | None = None, *, tenant: str = "") -> dict:
    """Exakt det som SKULLE levereras — utan att något levereras.

    Det är generatorns kärna: kunden ser bytes, media_type och
    förbehållen i filen INNAN ett schema sparas. Vägrade format ger
    exportmotorns eget besked (PDF: skälet, inte tystnaden).
    """
    try:
        ut = export(dataset_id, format, params or {}, tenant=tenant)
    except ExportRefused as e:
        raise PushRefused(str(e)) from e
    return {"dataset": dataset_id, "format": format,
            "media_type": FORMATS[format]["media_type"],
            "bytes": len(ut["content"].encode("utf-8")),
            "content": ut["content"],
            "meta": ut.get("meta", {}),
            "delivered": False,
            "note_en": "Preview only. Nothing was sent anywhere — save "
                       "the subscription (POST /v1/schedules, kind "
                       "'push') to deliver on a cadence."}


# ── Leveransen (körs av schemaläggaren) ────────────────────────────────
def _http_post(url: str, body: bytes, headers: dict,
               timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.status, r.read()


def deliver(job: dict, *, transport: Callable | None = None,
            timeout: float = 20.0) -> dict:
    """Kör prenumerationen EN gång: bygg innehållet, POST:a det, skriv
    sanningen om vad som hände."""
    p = job.get("params") or {}
    extra_huvud: dict = {}
    if p.get("connection"):
        # Kopplingen slås upp vid VARJE leverans: en roterad nyckel i
        # kryp-in gäller nästa natt utan att jobbet rörs, och
        # hemligheten bor kvar i lagret som maskerar den.
        from engine.connections import (ConnectionRefused, get_connection,
                                        headers_for, target_url_of)
        try:
            kopp = get_connection(p["connection"],
                                  tenant=job.get("tenant", ""))
            mal = target_url_of(kopp)
            extra_huvud = headers_for(kopp)
        except ConnectionRefused as e:
            return {"delivered": False, "status": None,
                    "why_en": (f"the {p['connection']!r} connection is "
                               f"gone or unusable: {e} — nothing was "
                               f"sent, and nothing is reported as "
                               f"sent")}
    else:
        mal = p.get("target_url", "")
        validate_target(mal)                # även i körningen: params kan
        #                                     ha ändrats efter skapandet
    inneh = preview(p.get("dataset", ""), p.get("format", "csv"),
                    p.get("dataset_params") or {},
                    tenant=job.get("tenant", ""))
    huvud = {"Content-Type": inneh["media_type"],
             "User-Agent": "landvex-push/1.0",
             "X-Landvex-Dataset": inneh["dataset"],
             **{k: v for k, v in extra_huvud.items()
                if k != "content-type"}}
    t = transport or _http_post
    try:
        status, _svar = t(mal, inneh["content"].encode("utf-8"), huvud,
                          timeout)
    except OUR_BUGS:
        raise
    except Exception as e:                                  # noqa: BLE001
        return {"delivered": False, "status": None,
                "why_en": (f"never got there: {type(e).__name__}: {e} — "
                           f"the network stopped the call"
                           if unreachable(e) else
                           f"the receiver refused: {type(e).__name__}: {e}"),
                "dataset": inneh["dataset"], "format": inneh["format"],
                "bytes": inneh["bytes"]}
    ok = 200 <= status < 300
    return {"delivered": ok, "status": status,
            "why_en": "" if ok else f"receiver answered HTTP {status} — "
                                    f"that is their word, and it stands",
            "dataset": inneh["dataset"], "format": inneh["format"],
            "bytes": inneh["bytes"]}


# ── Katalogen (generatorns valrymd) ────────────────────────────────────
def catalog() -> dict:
    exp = export_catalog()
    return {
        "what_en": ("Generate your own delivery: pick a dataset, a media "
                    "format and a webhook target, preview the exact "
                    "payload, then save it as a scheduled push. A "
                    "subscription IS a scheduled job (kind 'push') — the "
                    "same registry, claim logic and run history as every "
                    "other unattended run."),
        "datasets": exp["datasets"],
        "formats": [{"id": fid, **{k: v for k, v in f.items()}}
                    for fid, f in FORMATS.items()],
        "refused_formats": [{"id": fid, "why_en": skal}
                            for fid, skal in REFUSED_FORMATS.items()],
        "target_rules_en": ("https only; loopback and private addresses "
                            "are refused when the subscription is "
                            "created — a customer webhook must not "
                            "become a path into our own network."),
        "cannot_en": ("Delivery is at-least-once per cadence window, not "
                      "exactly-once: a receiver that answers slowly may "
                      "see a retry next window. The push carries the "
                      "file's own caveats but cannot make the receiver "
                      "read them."),
    }
