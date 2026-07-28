"""Leta efter samband och motsägelser — och vägra när underlaget inte bär.

Plattformen kunde redan RÄKNA ett samband (`engine/correlate.py`) och
ett kontradiktionsindex för en plats (`engine/indices.py`). Vad som
saknades var någon som **letade**: svepte en marknad, hittade var
planerat och observerat går isär, och lade fynden i ett register någon
kan öppna i efterhand.

Den som söker samband i många par hittar alltid några. Med 67 signaler
finns över tvåtusen par, och vid p<0,05 väntas hundra falska träffar av
ren slump. Modulen skyddar mot det på fyra sätt, och alla fyra står i
svaret:

  * **Mock mot mock rapporteras aldrig.** Två simulerade serier
    korrelerar precis som motorn konstruerade dem. Ett "samband" där är
    ett eko av vår egen generator, och att publicera det vore det
    värsta enskilda felet den här modulen kunde göra.
  * **Antalet prövade par följer med varje fynd.** Ett samband ur tio
    prövade och ett ur tvåtusen är inte samma påstående.
  * **n redovisas.** Under `MIN_N` regioner rapporteras ingenting alls.
  * **Aldrig ett kausalt ord.** `correlate.CAVEAT` och
    `framing_disclosure` följer med oförändrade.

Motsägelser är den andra halvan, och de är starkare bevis än samband:
när det officiella pappersarbetet säger en sak och marken en annan är
det ett fynd även om bara en enda plats visar det.

Fynden dedupliceras på checksumma, precis som bevakningsfynden — samma
motsägelse två dygn i rad är ett fynd, inte två.

Rent stdlib.
"""
from __future__ import annotations

import threading as _threading

from engine.claims import canonical_hash
from engine.correlate import CAVEAT, cross_domain, framing_disclosure

# Under så här många regioner rapporteras ingenting. En korrelation på
# fem punkter är en linje genom brus.
MIN_N = 12

# Hur stark en korrelation måste vara för att alls skrivas ned. Lägre än
# så är den inte ett fynd, den är en påminnelse om att brus finns.
MIN_R = 0.5

KINDS = ("contradiction", "relationship")


def _mock(sv) -> bool:
    return getattr(sv, "source", "mock") == "mock"


def _default_resolver():
    """Samma källkedja som svepet använder.

    En sökning som tyst kör på bara mock hittar per definition ingenting
    — varje par blir mock mot mock och hoppas över. Den skulle rapportera
    'inga fynd' och se korrekt ut, vilket är precis den sortens tysta
    nedgradering doktrinen förbjuder.
    """
    from engine.datasources.adapters import production_sources
    from engine.datasources.base import Resolver
    from engine.datasources.mock import MockSource
    # INTE scoring._DEFAULT_RESOLVER: den är mock-only, och en sökning
    # som kör på bara mock hoppar över varenda par och rapporterar
    # "inga fynd" — ett svar som ser korrekt ut och betyder blind.
    return Resolver(production_sources() + [MockSource()])


# ── Motsägelser ─────────────────────────────────────────────────────────
def contradictions(market: str, *, resolver=None, limit: int = 0,
                   as_of: str = "") -> dict:
    """Var säger pappret en sak och marken en annan?

    Använder kontradiktionsindexet i `engine/indices.py` — planerat
    (bygglov, detaljplaner, tillåten area) mot observerat (byggd area,
    renoveringsindex). Ingen ny formel; det här är sökningen, inte
    måttet.
    """
    from engine.indices import (CONTRADICTION_THRESHOLD, _OBSERVED, _PLANNED,
                                city_assessment)
    from engine.markets import MARKETS

    if market not in MARKETS:
        raise ValueError(f"Unknown market: {market}")
    planerade = {sid for sid, _ in _PLANNED}
    observerade = {sid for sid, _ in _OBSERVED}
    regioner = MARKETS[market].regions[:limit or None]
    # `relationships` fick den här raden; sveparen efter motsägelser fick
    # den aldrig. Utan den föll city_assessment till scoring-modulens
    # mock-only-resolver, så VARENDA region rapporterades som "allt
    # simulerat" — även efter att sju amerikanska bygglovsregister låg
    # skördade i lagret. En sökning som inte ser det vi faktiskt hämtat
    # hem säger "inget hittat" om sig själv, inte om världen.
    res = resolver or _default_resolver()
    fynd, prövade, tunna, halva = [], 0, 0, 0
    for kod, namn, lat, lon in regioner:
        prövade += 1
        bed = city_assessment(kod, market=market, resolver=res)
        # Listan heter `index` i city_assessment. Med fel nyckel gav
        # sökningen tomt varje gång utan att någonsin säga att den inte
        # hittade indexet — en sökning som tyst letar på fel ställe är
        # värre än en som säger att den inte kan.
        rad = next((i for i in bed.get("index", [])
                    if i["index_id"] == "contradiction_index"), None)
        if rad is None:
            raise ValueError(
                f"city_assessment for {kod} carried no contradiction "
                f"index; the sweep will not report an empty result as "
                f"'nothing found'")
        # Ett index som helt vilar på mock är vår egen generator som
        # motsäger sig själv. Det räknas inte som ett fynd om världen.
        drivare = rad.get("drivare") or []
        kallor = {d.get("kalla") for d in drivare}
        if kallor <= {"mock", None}:
            tunna += 1
            continue
        # Och ETT verkligt värde räcker inte. Indexet är en JÄMFÖRELSE
        # mellan två sidor; är den ena sidan simulerad mäter avståndet
        # vår generator, inte platsen. Mätt: med bara den observerade
        # sidan verklig rapporterades Solna som en kontradiktion på 36
        # med `sources: ["mock", "osm"]` — ett fynd om världen som helt
        # kom ur mockdata. Spärren måste därför gälla PER SIDA, och den
        # blir aktuell i samma stund som den första riktiga bygglovs-
        # källan kopplas in.
        akta = {d["signal_id"] for d in drivare
                if d.get("kalla") not in ("mock", None)}
        if not (akta & planerade) or not (akta & observerade):
            halva += 1
            continue
        if rad["varde"] < CONTRADICTION_THRESHOLD:
            continue
        fynd.append(_fynd("contradiction", market, kod, {
            "region": namn, "lat": lat, "lon": lon,
            "value": rad["varde"], "band": rad["band"],
            "sources": sorted(k for k in kallor if k),
            "detail_en": rad.get("narrativ_en", ""),
            "why_it_matters_en": (
                "Planned and observed disagree here. That is a finding "
                "about the place, not about the model: one of the two "
                "records is wrong, and which one it is cannot be settled "
                "from here."),
        }, as_of))
    return {
        "kind": "contradiction", "market": market,
        "findings": sorted(fynd, key=lambda f: -f["value"]),
        "count": len(fynd), "regions_examined": prövade,
        "skipped_all_mock": tunna,
        "skipped_one_sided": halva,
        "threshold": CONTRADICTION_THRESHOLD,
        "means_en": (
            "Where the official paperwork and the observed ground differ "
            "by more than the threshold. A single region is enough — a "
            "contradiction does not need a sample to be real."),
        "cannot_en": (
            "It cannot say WHICH side is wrong. An unbuilt permit and an "
            "unpermitted build look identical in the index, and telling "
            "them apart needs a look at the place."),
        "skipped_en": (f"{tunna} region(s) skipped: every driver was "
                       f"simulated, and our own generator contradicting "
                       f"itself is not a finding about the world. "
                       f"{halva} more skipped because only ONE side of "
                       f"the comparison was real — measuring real ground "
                       f"against simulated paperwork measures the "
                       f"simulation."),
    }


# ── Samband ─────────────────────────────────────────────────────────────
def relationships(market: str, signal_pairs: list[tuple[str, str]] | None = None,
                  *, resolver=None, limit: int = 0, as_of: str = "") -> dict:
    """Vilka signaler rör sig ihop över regionerna i en marknad?

    Tvärsnitt, inte tidsserie: en punkt per region. Det är den enda
    riktning som går att köra i dag — plattformen har ännu ingen
    historik att korrelera över tid, och att låtsas annat vore att
    uppfinna en tidsaxel.
    """
    from engine.markets import MARKETS
    from engine.models import Location
    from engine.signals import CATALOG

    if market not in MARKETS:
        raise ValueError(f"Unknown market: {market}")
    regioner = MARKETS[market].regions[:limit or None]
    serier: dict[str, list[float]] = {}
    kallor: dict[str, set] = {}
    res = resolver or _default_resolver()
    alla = sorted(CATALOG)
    for _kod, _namn, lat, lon in regioner:
        # Vertikalen är bara en nyckel för källorna; sökningen gäller
        # signalerna själva, så alla hämtas för samma punkt.
        varden, _ = res.resolve(Location(lat, lon), "gym", alla)
        for sid, sv in varden.items():
            if sv is None or sv.value is None:
                continue
            serier.setdefault(sid, []).append(float(sv.value))
            kallor.setdefault(sid, set()).add(getattr(sv, "source", "mock"))

    hela = [s for s, v in serier.items() if len(v) == len(regioner)]
    par = signal_pairs or [(a, b) for i, a in enumerate(sorted(hela))
                           for b in sorted(hela)[i + 1:]]
    fynd, prövade, mock_par = [], 0, 0
    for a, b in par:
        if a not in serier or b not in serier:
            continue
        n = min(len(serier[a]), len(serier[b]))
        if n < MIN_N:
            continue
        prövade += 1
        # Mock mot mock: ett eko av vår egen generator.
        if kallor.get(a, {"mock"}) <= {"mock"} and \
                kallor.get(b, {"mock"}) <= {"mock"}:
            mock_par += 1
            continue
        r = cross_domain(serier[a][:n], serier[b][:n], label_a=a, label_b=b)
        if abs(r["pearson"]) < MIN_R:
            continue
        fynd.append(_fynd("relationship", market, f"{a}~{b}", {
            "pair": [a, b], "n": n,
            "pearson": r["pearson"], "spearman": r["spearman"],
            "direction": r["direction"], "confidence": r["confidence"],
            "spurious_warning": r["spurious_warning"],
            "sources": {a: sorted(kallor.get(a, [])),
                        b: sorted(kallor.get(b, []))},
            "detail_en": (f"{a} and {b} move {r['direction']}ly together "
                          f"across {n} region(s) (r={r['pearson']})."),
        }, as_of))
    for f in fynd:
        # Ett samband ur tio prövade par och ett ur tvåtusen är inte
        # samma påstående. Talet står på VARJE fynd, inte bara i en
        # sammanfattning någon kan klippa bort.
        f["pairs_tested"] = prövade
    return {
        "kind": "relationship", "market": market,
        "findings": sorted(fynd, key=lambda f: -abs(f["pearson"])),
        "count": len(fynd), "pairs_tested": prövade,
        "skipped_all_mock": mock_par, "regions": len(regioner),
        "min_n": MIN_N, "min_r": MIN_R,
        # Vilka källor som faktiskt svarade. Utan det kan en körning där
        # allt var mock inte skiljas från en där inget samband fanns.
        "sources_seen": sorted({k for v in kallor.values() for k in v}),
        "caveat": CAVEAT, "framing": framing_disclosure(),
        "means_en": (
            "Signals that move together across the regions of one market. "
            "A cross-section, not a time series: the platform has no "
            "history to correlate over yet, and inventing a time axis "
            "would be worse than saying so."),
        "cannot_en": (
            "Correlation across places is not a mechanism. Two signals "
            "can move together because a third moves both, and searching "
            "many pairs finds some by chance — pairs_tested is on every "
            "finding so the reader can judge that themselves."),
        "skipped_en": (f"{mock_par} pair(s) skipped where BOTH signals "
                       f"were simulated. Two mock series correlate exactly "
                       f"as the generator built them."),
    }


# ── Registret ───────────────────────────────────────────────────────────
_LOCK = _threading.Lock()
_FYND: list[dict] = []


def _fynd(kind: str, market: str, scope: str, detalj: dict,
          as_of: str) -> dict:
    rec = {"kind": kind, "market": market, "scope": scope,
           "as_of": as_of, **detalj}
    rec["checksum"] = canonical_hash(
        {"kind": kind, "market": market, "scope": scope,
         "detail": detalj.get("detail_en", "")})
    return rec


def record(findings: list[dict]) -> int:
    """Lägg fynden i registret. Dedup på checksumma: samma motsägelse två
    dygn i rad är ETT fynd, inte två."""
    nya = 0
    with _LOCK:
        sedda = {f["checksum"] for f in _FYND}
        for f in findings:
            if f["checksum"] in sedda:
                continue
            sedda.add(f["checksum"])
            _FYND.append(f)
            nya += 1
    return nya


def register(kind: str = "", market: str = "") -> dict:
    """Rapportregistret — vad sökningen har hittat, och vad den inte kan."""
    rader = [f for f in _FYND
             if (not kind or f["kind"] == kind)
             and (not market or f["market"] == market)]
    per: dict[str, int] = {}
    for f in rader:
        per[f["kind"]] = per.get(f["kind"], 0) + 1
    return {
        "findings": rader, "count": len(rader), "by_kind": per,
        "kinds": list(KINDS),
        "quiet_en": ("Nothing found yet. An empty register after a run is "
                     "a result: it means the sweep looked and found "
                     "nothing above the thresholds, which is different "
                     "from never having looked."
                     if not rader else ""),
        "cannot_en": (
            "A register of findings is not a register of truths. Each row "
            "says what was measured, how many regions it rests on, and "
            "how many pairs were tested to find it — and none of them is "
            "a claim about cause."),
    }


def reset() -> None:
    """Endast för tester."""
    with _LOCK:
        _FYND.clear()


def run(market: str, *, resolver=None, limit: int = 0,
        as_of: str = "") -> dict:
    """Kör hela sökningen för en marknad och lägg fynden i registret."""
    m = contradictions(market, resolver=resolver, limit=limit, as_of=as_of)
    s = relationships(market, resolver=resolver, limit=limit, as_of=as_of)
    nya = record(m["findings"]) + record(s["findings"])
    return {
        "market": market, "new_findings": nya,
        "contradictions": {k: v for k, v in m.items() if k != "findings"},
        "relationships": {k: v for k, v in s.items() if k != "findings"},
        "found": m["count"] + s["count"],
        "means_en": ("new_findings counts what was not already in the "
                     "register. A run that finds the same contradiction "
                     "as yesterday adds nothing, and that is the point."),
    }


def catalog() -> dict:
    return {
        "kinds": [
            {"id": "contradiction",
             "label_en": "Planned says one thing, the ground says another",
             "needs_en": "One region is enough.",
             "from_en": "/v1/indices/assess (contradiction_index)"},
            {"id": "relationship",
             "label_en": "Signals that move together across places",
             "needs_en": f"At least {MIN_N} regions and |r| ≥ {MIN_R}.",
             "from_en": "/v1/correlate"},
        ],
        "min_n": MIN_N, "min_r": MIN_R,
        "principle_en": (
            "Whoever searches many pairs will always find some. Every "
            "finding therefore carries how many pairs were tested and how "
            "many regions it rests on, and no pair where BOTH signals are "
            "simulated is ever reported — two mock series correlate "
            "exactly as the generator built them."),
        "cannot_en": (
            "Nothing here is causal, and the words never suggest it is. "
            "A contradiction says the two records disagree, not which one "
            "is wrong."),
    }
