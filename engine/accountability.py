"""Ansvarsloopen – beslut → ägare → förväntat utfall → faktiskt utfall.

Syntesen av två invändningar: Gudrun ("ansvarsflykt via arkitektur") och
Jacob Wallenberg ("politikerns reflex, inte ägarens"). Svaret är att göra
BESLUTET självt till ett versionerat, ägar-signerat påstående med ett
förväntat utfall – och sedan stänga loopen mot verkligheten. "Vem bär
utfallet" blir en rad i databasen, inte en replik i en debatt.

  * `commit` – ett beslut MÅSTE ha tre ansvarsroller (NOGF), annars får det
    inte finnas. Innehållshashat id, förväntat utfall (metric/riktning/mål).
  * `resolve` – jämför faktiskt utfall mot det förväntade, riktnings-medvetet;
    beräknar `met` + avvikelse + effektivitet. Append-only.
  * `ledger` – ansvarskort per ägare: hur många beslut, hur många infriade,
    snitt-effektivitet. Förvaltarskap som data.

Rent stdlib. Persisteras via Store (delas över workers, överlever omstart);
faller ärligt tillbaka på process-minne. Återanvänder claims-governance +
integrity-hash.
"""
from __future__ import annotations

import threading

from .claims import validate_governance
from .integrity import canonical_hash, framing_disclosure
from .stats import mean

_DECISIONS: list[dict] = []
_RESOLUTIONS: list[dict] = []
_LOCK = threading.Lock()
_STORE = None


def set_store(store) -> None:
    """Backa loopen med ett Store (läsande stödprov, ingen skräpskrivning)."""
    global _STORE
    _STORE = store if (store is not None
                       and getattr(store, "all_decisions", lambda: None)()
                       is not None) else None


def commit(decision: str, owners: dict, expected: dict, *,
           kpi_ids: list | None = None, horizon_months: int = 0,
           committed_at: str = "") -> dict:
    """Registrera ett beslut. Kräver tre ansvarsroller (formellt/operativt/
    uppfoljning) och ett förväntat utfall {metric, direction, target}.

    direction ∈ {increase, decrease, reach}. Höjer ValueError vid brott –
    ett beslut utan ägare får inte finnas (NOGF).
    """
    ok, missing = validate_governance({"owners": owners})
    if not ok:
        raise ValueError(f"decision needs owners {missing} — no owner, no decision")
    for f in ("metric", "direction", "target"):
        if f not in expected:
            raise ValueError(f"expected outcome missing '{f}'")
    if expected["direction"] not in ("increase", "decrease", "reach"):
        raise ValueError("direction must be increase|decrease|reach")
    rec = {"decision": decision, "owners": dict(owners),
           "expected": dict(expected), "kpi_ids": list(kpi_ids or []),
           "horizon_months": int(horizon_months),
           "committed_at": committed_at, "status": "open", "version": 1}
    rec["id"] = canonical_hash({k: rec[k] for k in
                                ("decision", "owners", "expected",
                                 "committed_at")})
    _save_decision(rec)
    return rec


def resolve(commitment: dict, actual_value: float, *,
            baseline: float | None = None, resolved_at: str = "") -> dict:
    """Stäng loopen: jämför faktiskt utfall mot det förväntade.

    Returnerar en (append-only) resolution: met, deviation_pct, effectiveness
    (0–100). effectiveness mäter framsteg baseline→mål om baseline ges, annars
    100 vid infriat / avtar med avvikelsen.
    """
    exp = commitment["expected"]
    target = float(exp["target"])
    d = exp["direction"]
    a = float(actual_value)
    if d == "increase":
        met = a >= target
    elif d == "decrease":
        met = a <= target
    else:  # reach
        met = (abs(a - target) / abs(target)) <= 0.05 if target else a == target
    dev = ((a - target) / abs(target) * 100.0) if target else 0.0
    if baseline is not None and target != baseline:
        prog = (a - baseline) / (target - baseline) * 100.0
        effectiveness = round(max(0.0, min(100.0, prog)), 2)
    else:
        effectiveness = 100.0 if met else round(max(0.0, 100.0 - abs(dev)), 2)
    res = {"decision_id": commitment["id"], "expected": exp,
           "actual": a, "met": bool(met), "deviation_pct": round(dev, 4),
           "effectiveness": effectiveness, "resolved_at": resolved_at,
           "owner": commitment["owners"].get("formellt", ""),
           # "Statistik ljuger alltid": 'met' är ett svar oavsett utfall –
           # redovisa ramen (mål/riktning/baslinje) som gjorde det till ett.
           "framing": framing_disclosure({"target": target, "direction": d,
                                          "baseline": baseline,
                                          "met_defined_by": commitment["owners"]
                                          .get("formellt", "owner")})}
    res["id"] = canonical_hash({"decision_id": res["decision_id"],
                                "actual": a, "resolved_at": resolved_at})
    _save_resolution(res)
    return res


def ledger(owner: str | None = None) -> dict:
    """Ansvarskort. Utan `owner`: per formellt ansvarig. Med `owner`: den enes.

    För varje ägare: antal beslut, öppna, infriade, infriandegrad och
    snitt-effektivitet – "vem bär utfallet" summerat.
    """
    decisions = _all_decisions()
    resolutions = _all_resolutions()
    res_by_dec = {r["decision_id"]: r for r in resolutions}
    rows: dict[str, dict] = {}
    for dcn in decisions:
        who = dcn["owners"].get("formellt", "(unassigned)")
        if owner and who != owner:
            continue
        row = rows.setdefault(who, {"owner": who, "decisions": 0, "resolved": 0,
                                    "met": 0, "open": 0, "_eff": []})
        row["decisions"] += 1
        r = res_by_dec.get(dcn["id"])
        if r is None:
            row["open"] += 1
        else:
            row["resolved"] += 1
            row["met"] += 1 if r["met"] else 0
            row["_eff"].append(r["effectiveness"])
    out = []
    for row in rows.values():
        eff = row.pop("_eff")
        row["met_rate"] = round(row["met"] / row["resolved"], 4) if row["resolved"] else None
        row["avg_effectiveness"] = round(mean(eff), 2) if eff else None
        out.append(row)
    out.sort(key=lambda x: (-(x["avg_effectiveness"] or -1), x["owner"]))
    return {"ledger": out, "total_decisions": len(decisions),
            "total_resolved": len(resolutions),
            "framing": framing_disclosure(
                {"met_rate_depends_on": "targets each owner set themselves",
                 "unresolved_excluded": True})}


# --- lager (store eller process-minne) -----------------------------------
def _save_decision(rec: dict) -> str:
    if _STORE is not None:
        return _STORE.save_decision(rec)
    with _LOCK:
        if not any(d["id"] == rec["id"] for d in _DECISIONS):
            _DECISIONS.append(rec)
    return rec["id"]


def _save_resolution(rec: dict) -> str:
    if _STORE is not None:
        return _STORE.save_resolution(rec)
    with _LOCK:
        if not any(r["id"] == rec["id"] for r in _RESOLUTIONS):
            _RESOLUTIONS.append(rec)
    return rec["id"]


def _all_decisions() -> list[dict]:
    return _STORE.all_decisions() if _STORE is not None else list(_DECISIONS)


def _all_resolutions() -> list[dict]:
    return _STORE.all_resolutions() if _STORE is not None else list(_RESOLUTIONS)


def all_decisions() -> list[dict]:
    """Alla åtagna beslut (store eller process-minne). Publik läsning så
    andra lager – t.ex. händelseroutningen – slipper nå interna funktioner."""
    return _all_decisions()


def get_decision(decision_id: str) -> dict | None:
    for d in _all_decisions():
        if d["id"] == decision_id:
            return d
    return None


def reset() -> None:
    """Nollställ process-minnet (test). Rör inte ett persistent store."""
    _DECISIONS.clear()
    _RESOLUTIONS.clear()
