"""Det som faktiskt väcker plattformen.

`engine/scheduler.py` vet VAD som ska köras och när. Den vet inte hur man
väntar, och ska inte veta det: en tråd hör hemma i API-lagret, inte i en
beroendefri kärna vars hela poäng är att samma anrop ger samma svar.

**Avstängd som standard.** En bakgrundstråd som startar bara för att
någon importerat en modul är en överraskning, och en överraskning som
beställer fältuppdrag åt en kund är en dyr sådan. Sätt
`LANDVEX_SCHEDULER=on` för att slå på den.

**En instans, eller ett lager.** Tråden kör `scheduler.run_due()` för
ALLA kunder. Kör två instanser utan gemensamt lager tar ingen av dem
jobbet ifrån den andra — därför claimar `scheduler` i lagret när det
finns ett, och säger rakt ut i svaret när det inte gör det.

Produktionsalternativet är samma sak utifrån: EventBridge (eller cron)
som slår på `POST /v1/schedules/run`. Se `deploy/aws/scheduler-rule.json`.

Rent stdlib.
"""
from __future__ import annotations

import os
import threading
import time
import traceback

_TRAD: threading.Thread | None = None
_STOPP = threading.Event()
_SENAST: dict = {"at": 0.0, "ran": 0, "error": ""}


def enabled() -> bool:
    return os.environ.get("LANDVEX_SCHEDULER", "off").lower() in (
        "on", "1", "true", "yes")


def interval_s() -> float:
    try:
        return max(5.0, float(os.environ.get(
            "LANDVEX_SCHEDULER_INTERVAL_S", "60")))
    except ValueError:
        return 60.0


def _varv() -> None:
    from engine import scheduler

    while not _STOPP.wait(interval_s()):
        try:
            r = scheduler.run_due()          # alla kunder
            _SENAST.update({"at": time.time(), "ran": r["ran_count"],
                            "error": ""})
        except Exception as e:                            # noqa: BLE001
            # En tråd som dör tyst är värre än ett fel som syns: nästa
            # varv ska fortfarande komma, och felet ska stå i /v1/schedules.
            _SENAST.update({"at": time.time(), "ran": 0,
                            "error": f"{type(e).__name__}: {e}"})
            traceback.print_exc()


def start() -> bool:
    """Starta tickern om den är påslagen. Idempotent."""
    global _TRAD
    if not enabled() or (_TRAD is not None and _TRAD.is_alive()):
        return _TRAD is not None and _TRAD.is_alive()
    _STOPP.clear()
    _TRAD = threading.Thread(target=_varv, name="landvex-ticker",
                             daemon=True)
    _TRAD.start()
    return True


def stop() -> None:
    _STOPP.set()


def status() -> dict:
    kor = _TRAD is not None and _TRAD.is_alive()
    return {"scheduler": {
        "enabled": enabled(),
        "running": kor,
        "interval_s": interval_s(),
        "last_tick": _SENAST,
        "how_en": (
            f"In-process ticker every {interval_s():.0f}s."
            if kor else
            "Not running. Set LANDVEX_SCHEDULER=on for the in-process "
            "ticker, or point EventBridge/cron at POST /v1/schedules/run "
            "— the endpoint does the same work and is the right choice "
            "for more than one instance."),
    }}
