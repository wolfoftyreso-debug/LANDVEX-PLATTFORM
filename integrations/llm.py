"""Kundens egen språkmodell och egna kanaler — proben och berättaren.

Motorn (engine/connections.py) äger katalogen och lagringen; DET HÄR
lagret är det enda som faktiskt ringer ut. Två operationer:

* **probe(rec)** — bevisa att kopplingen FUNGERAR: leverantörens
  riktiga server ska svara. `verified` blir aldrig sant av att nyckeln
  ser rätt ut, av en DNS-träff eller av ett policyblock — bara av ett
  riktigt svar. Utan nät är svaret en vägran med skälet, inte ett
  hoppfullt "antagligen ok". För webhooks postas ett tydligt märkt
  testmeddelande — det SYNS i kundens kanal, vilket är poängen: ett
  test ingen ser bevisar ingenting om leveransvägen.
* **narrate(rec, ...)** — låt kundens EGEN modell tolka en Landvex-
  analys, fakturerat på kundens egen nyckel. Svaret är märkt som
  modellens tolkning och lagras aldrig som fakta: siffrorna är våra,
  orden är modellens, och de två får inte blandas ihop.

Transporten är injicerbar (testbar mot fixtur, ingen mock av urllib);
nycklar loggas aldrig och ingår aldrig i felmeddelanden. Rent stdlib —
API-anropen är rå HTTP eftersom kärnan inte tar beroenden.
"""
from __future__ import annotations

import json
import time as _time
import urllib.error
import urllib.request
from typing import Callable

from engine.connections import (DEFAULT_ANTHROPIC_MODEL,
                                ConnectionRefused)
from engine.datasources.faults import OUR_BUGS

_TIMEOUT = 20.0
_ANTHROPIC_VERSION = "2023-06-01"


def _http(url: str, headers: dict, body: bytes | None,
          timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(
        url, data=body, headers=headers,
        method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.status, r.read()


# ── Requestbyggarna: per leverantör, som data-formade funktioner ───────
def _anthropic_narrate(cfg: dict, prompt: str) -> tuple[str, dict, bytes]:
    body = {
        "model": cfg.get("model") or DEFAULT_ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    return ("https://api.anthropic.com/v1/messages",
            {"x-api-key": cfg["api_key"],
             "anthropic-version": _ANTHROPIC_VERSION,
             "content-type": "application/json"},
            json.dumps(body).encode("utf-8"))


def _anthropic_text(svar: dict) -> str:
    if svar.get("stop_reason") == "refusal":
        return ("[The connected model declined this request for safety "
                "reasons — that is the model's own answer, relayed "
                "as-is.]")
    return "".join(b.get("text", "") for b in svar.get("content", [])
                   if b.get("type") == "text")


def _openai_narrate(cfg: dict, prompt: str) -> tuple[str, dict, bytes]:
    body = {
        "model": cfg.get("model") or "gpt-4o",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    return ("https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {cfg['api_key']}",
             "content-type": "application/json"},
            json.dumps(body).encode("utf-8"))


def _openai_text(svar: dict) -> str:
    val = (svar.get("choices") or [{}])[0]
    return (val.get("message") or {}).get("content") or ""


_LLM = {
    "anthropic": (_anthropic_narrate, _anthropic_text),
    "openai": (_openai_narrate, _openai_text),
}

# Proben per leverantör: billigaste anropet som ändå kräver giltig
# nyckel. För webhooks: ett märkt testmeddelande — synligt med flit.
_PROBES: dict[str, Callable[[dict], tuple[str, dict, bytes | None]]] = {
    "anthropic": lambda cfg: (
        "https://api.anthropic.com/v1/models",
        {"x-api-key": cfg["api_key"],
         "anthropic-version": _ANTHROPIC_VERSION}, None),
    "openai": lambda cfg: (
        "https://api.openai.com/v1/models",
        {"Authorization": f"Bearer {cfg['api_key']}"}, None),
    "slack_webhook": lambda cfg: (
        cfg["webhook_url"], {"content-type": "application/json"},
        json.dumps({"text": "Landvex connection test — if you can read "
                            "this, the delivery path works. Nothing "
                            "else follows."}).encode("utf-8")),
    "teams_webhook": lambda cfg: (
        cfg["webhook_url"], {"content-type": "application/json"},
        json.dumps({"text": "Landvex connection test — if you can read "
                            "this, the delivery path works. Nothing "
                            "else follows."}).encode("utf-8")),
}


def probe(rec: dict, *, transport: Callable | None = None) -> dict:
    """Fungerar kopplingen? Bara ett riktigt svar räknas.

    Returnerar {verified, status, why_en, probed_at}. `verified` är
    sant ENDAST när leverantörens server svarade 2xx — ett nätfel, ett
    policyblock eller en timeout är `verified: False` med skälet, och
    det skälet skiljer på "nyckeln är fel" (4xx från leverantören) och
    "vi kom inte fram" (inget svar alls). Nyckeln ingår aldrig i
    felmeddelandet.
    """
    bygg = _PROBES.get(rec.get("provider", ""))
    if bygg is None:
        raise ConnectionRefused(
            f"no probe defined for provider {rec.get('provider')!r}")
    url, headers, body = bygg(rec.get("config") or {})
    sand = transport or _http
    nu = _time.time()
    try:
        status, _ = sand(url, headers, body, _TIMEOUT)
    except urllib.error.HTTPError as e:
        # Leverantören SVARADE — med ett nej. Det är information:
        # vägen fram fungerar, nyckeln/webhooken gör det inte.
        return {"verified": False, "status": e.code, "probed_at": nu,
                "why_en": (f"the provider answered HTTP {e.code} — the "
                           f"network path works, but the credential was "
                           f"not accepted. That is the provider's word, "
                           f"and it stands.")}
    except OUR_BUGS:
        raise
    except Exception as e:  # noqa: BLE001 — nätranden: varje fel HÄR
        # är exakt det proben finns för att upptäcka; våra egna buggar
        # har redan släppts igenom ovan.
        return {"verified": False, "status": 0, "probed_at": nu,
                "why_en": (f"no answer from the provider "
                           f"({type(e).__name__}) — nothing was "
                           f"verified. A connection is not 'probably "
                           f"fine': until the real server answers, its "
                           f"status stays 'configured'.")}
    ok = 200 <= status < 300
    return {"verified": ok, "status": status, "probed_at": nu,
            "why_en": ("the provider's real server answered — the key "
                       "works as of this probe, which says nothing "
                       "about tomorrow." if ok else
                       f"the provider answered HTTP {status}, which is "
                       f"not a yes.")}


def narrate(rec: dict, analysis: dict, *, question: str = "",
            transport: Callable | None = None) -> dict:
    """Kundens egen modell tolkar en Landvex-analys.

    Prompten bär analysens JSON och dess förbehåll; svaret är märkt som
    MODELLENS tolkning, fakturerad på kundens nyckel, aldrig lagrad som
    fakta.
    """
    par = _LLM.get(rec.get("provider", ""))
    if par is None:
        raise ConnectionRefused(
            f"{rec.get('provider')!r} is not a language model "
            f"connection — narration needs one of "
            f"{', '.join(sorted(_LLM))}")
    bygg, las = par
    prompt = (
        "You are interpreting a decision-support analysis for a "
        "customer of the Landvex platform. The JSON below carries its "
        "own caveats and data coverage — treat them as binding: do not "
        "invent numbers, do not soften stated limitations, and say "
        "plainly when the data cannot answer something.\n\n"
        + json.dumps(analysis, ensure_ascii=False, default=str)[:20000]
        + ("\n\nThe customer's question: " + question if question
           else "\n\nSummarize what this analysis supports, and what "
                "it does not."))
    url, headers, body = bygg(rec.get("config") or {}, prompt)
    sand = transport or _http
    try:
        status, ra = sand(url, headers, body, _TIMEOUT)
    except urllib.error.HTTPError as e:
        raise ConnectionRefused(
            f"the provider answered HTTP {e.code} — the narration did "
            f"not happen, and no text was invented in its place. Run "
            f"the connection test (POST /v1/connections/test) to see "
            f"whether the credential still works.") from e
    except OUR_BUGS:
        raise
    except Exception as e:  # noqa: BLE001 — nätranden, samma skäl som
        # i probe(): felet ÄR resultatet, och det får inte se ut som
        # en tyst tom berättelse.
        raise ConnectionRefused(
            f"no answer from the provider ({type(e).__name__}) — the "
            f"narration did not happen. Nothing was invented in its "
            f"place.") from e
    svar = json.loads(ra.decode("utf-8"))
    text = las(svar)
    return {
        "provider": rec["provider"],
        "model": svar.get("model") or (rec.get("config") or {}).get(
            "model", ""),
        "text": text,
        "status": status,
        "what_this_is_en": (
            "Interpretation from the customer's OWN connected model, "
            "billed to their key. It is commentary on the analysis — "
            "never a Landvex measurement, and it is not stored as "
            "fact."),
    }
