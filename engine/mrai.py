"""Media Reality Alignment Index — och vägran där vi inte kan se.

Hur väl stämmer ett lands nyhetsrapportering med verifierbara händelser?
Frågan är rätt ställd och farlig att svara på. Den här modulen svarar på
den där den kan, och **vägrar där den inte kan** — för det finns exakt
ett sätt att göra ett sådant här index skadligt, och det är det här:

    Vi har referensdata för Sverige och nästan ingen annanstans.
    `/v1/coverage` mäter real_weight 0,0 för 34 av 35 marknader.

Ett index som körs på det underlaget ger **låg alignment åt länder där
VI saknar referensdata** — inte åt länder där medierna avviker. Ett land
med svag statistikmyndighet skulle få dåligt betyg för att vi inte kan
se, och indexet blir en pressfrihetsranking som i själva verket mäter
vår egen täckning. Publicerat skulle det skada verkliga länder på
felaktig grund.

Därför: **under täckningströskeln finns inget indexvärde.** Inte ett
lågt — inget. Ett land utan referensdata får `status: "insufficient"`
och en lista över vad som saknas. Det är samma spärr som
`engine/analysis.py` har för mock-mot-mock, flyttad till landsnivå.

**Varje delindex öppnas.** Ingen komponent får bidra med ett tal utan
att kunna visa vad det vilar på, hur många källor, och vad det inte kan
avgöra. Ett index som inte går att öppna är ett omdöme med en siffra på.

Komponenterna räknas ur motorer som redan finns — det här lagret väger
ihop, det mäter inte själv:

    cross_source_agreement   engine/corroboration (nät, inte källor)
    independent_verification engine/news (ägare, inte titlar)
    source_diversity         engine/datasources/sensor_apis
    public_data_alignment    engine/indices (kontradiktionsindexet)
    event_coverage_ratio     engine/news.attention_index
    reference_coverage       engine/coverage (vår EGEN täckning)

Rent stdlib.
"""
from __future__ import annotations

# Under den här andelen verklig referensdata beräknas INGET index för
# landet. Tröskeln är låg med flit — den ska stoppa det uppenbart
# ogrundade, inte kräva perfektion — men den är absolut.
MIN_REFERENCE_COVERAGE = 0.10

# Ett delindex behöver minst så här många oberoende nät för att räknas.
MIN_NETWORKS = 2

# Hur stor andel av den avsedda vikten som måste gå att räkna. Ett index
# byggt på en fjärdedel av sina komponenter är nästan lika vilseledande
# som ett byggt på ingenting: talet ser likadant ut, och läsaren kan inte
# se skillnaden utan att öppna det. Under tröskeln redovisas
# komponenterna — men inget sammanvägt tal.
MIN_WEIGHT_COMPUTED = 0.5


def _pct(x: float) -> float:
    return round(max(0.0, min(100.0, 100.0 * x)), 1)


# ── Komponenterna ───────────────────────────────────────────────────────
# Vikterna är en DOKUMENTERAD HEURISTIK, inte en härledd sanning. De står
# här så att den som är oense kan peka på raden i stället för att gissa.
COMPONENTS: tuple[dict, ...] = (
    {"id": "reference_coverage", "weight": 0.0,
     "label_en": "Reference coverage (gate, not a score)",
     "what_en": "How much of the signal picture we can actually see in "
                "this market. It scores nothing — it decides whether "
                "anything may be scored at all.",
     "cannot_en": "It says nothing about the country's media. It is a "
                  "statement about US."},
    {"id": "source_diversity", "weight": 0.25,
     "label_en": "Source diversity",
     "what_en": "How many INDEPENDENT networks can observe this market. "
                "One network cannot corroborate itself, however much it "
                "publishes.",
     "cannot_en": "Counting networks is not counting quality. Two "
                  "independent networks can both be wrong."},
    {"id": "independent_verification", "weight": 0.30,
     "label_en": "Independent verification",
     "what_en": "Of the reported claims, how many were carried by at "
                "least two independent OWNERS — not two titles.",
     "cannot_en": "Agreement between outlets is agreement about a "
                  "report, not about the world. Ten newsrooms can repeat "
                  "one wrong source."},
    {"id": "public_data_alignment", "weight": 0.30,
     "label_en": "Public data alignment",
     "what_en": "How often the official record and the observed ground "
                "agree, from the contradiction index.",
     "cannot_en": "A contradiction cannot say WHICH side is wrong. An "
                  "unbuilt permit and an unpermitted build look the same."},
    {"id": "event_coverage_ratio", "weight": 0.15,
     "label_en": "Event coverage ratio",
     "what_en": "Published against REPORTED, both per 100k inhabitants, "
                "compared with peer places.",
     "cannot_en": "Published against reported, never against occurred. "
                  "Propensity to report varies, and the dark figure is a "
                  "different size everywhere."},
)

_BY_ID = {c["id"]: c for c in COMPONENTS}


def _component(cid: str, value: float | None, basis: dict,
               refusal: str = "") -> dict:
    spec = _BY_ID[cid]
    return {
        "id": cid, "label_en": spec["label_en"],
        "what_en": spec["what_en"], "cannot_en": spec["cannot_en"],
        "weight": spec["weight"],
        "value": None if value is None else _pct(value),
        "status": "refused" if value is None else "computed",
        "refusal_en": refusal,
        "basis": basis,
    }


# ── Räkningen ───────────────────────────────────────────────────────────
def _reference_coverage(market: str) -> tuple[float, dict]:
    from engine.coverage import coverage

    c = coverage(market)
    return c["real_weight"], {
        "real_weight": c["real_weight"], "band": c["band"],
        "live_signals": c["signals"]["live"],
        "of_total": c["signals"]["total"],
        "what_would_change_it": [w["source"] for w
                                 in c["what_would_change_it"][:3]],
    }


def _source_diversity(market: str) -> tuple[float | None, dict, str]:
    from engine.datasources.sensor_apis import PROVIDERS

    per = {k: len(v) for k, v in PROVIDERS.items()}
    med_tva = [k for k, n in per.items() if n >= MIN_NETWORKS]
    andel = len(med_tva) / len(per) if per else 0.0
    return andel, {"classes": len(per), "with_two_or_more": len(med_tva),
                   "classes_named": sorted(med_tva)}, ""


def _independent_verification(market: str) -> tuple[float | None, dict, str]:
    from engine import news as N

    poster = N.all_items(market=market, max_age_days=N_WINDOW_DAYS)
    if not poster:
        return None, {"items": 0}, (
            "No reporting has been harvested for this market, so there is "
            "nothing to verify. That is an absence of INPUT, not a "
            "finding about the press.")
    # Klustret får innehålla globala telegram — de är oberoende röster —
    # men det måste innehålla minst EN rad från landets egen press.
    # Utan den regeln räknades ett Reuters-telegram som tysk verifiering.
    kluster = [k for k in N.cluster(poster)
               if any(i.get("market") == market for i in k["items"])]
    if not kluster:
        return None, {"items": len(poster), "clusters": 0}, (
            "Reporting was harvested, but none of it came from this "
            "market's own press — only global wire copy. A wire item is "
            "not this country's journalism, and counting it as such would "
            "score every country the same. Absence of INPUT, again.")
    bekraftade = [k for k in kluster if k["may_inform_analysis"]]
    andel = len(bekraftade) / len(kluster)
    return andel, {
        "clusters": len(kluster), "corroborated": len(bekraftade),
        "single_owner": len(kluster) - len(bekraftade),
        "owners_seen": sorted({o for k in kluster for o in k["owners"]}),
    }, ""


def _public_data_alignment(market: str, limit: int) -> tuple[float | None,
                                                             dict, str]:
    from engine.analysis import contradictions

    c = contradictions(market, limit=limit)
    # Halvt verkliga regioner räknas INTE som granskade. Ett index där
    # bara ena sidan är verklig mäter mocken, och att lägga dem i nämnaren
    # hade sänkt alignment för länder där vi kopplat in EN källa.
    granskade = (c["regions_examined"] - c["skipped_all_mock"]
                 - c.get("skipped_one_sided", 0))
    if granskade <= 0:
        return None, {"regions_examined": c["regions_examined"],
                      "skipped_all_mock": c["skipped_all_mock"],
                      "skipped_one_sided": c.get("skipped_one_sided", 0)}, (
            "No region had BOTH a real planned record and a real observed "
            "one. Where everything was simulated, our own generator "
            "contradicting itself says nothing about this country; where "
            "only one side was real, the distance measures the simulation. "
            "This component stays refused until an open permits or "
            "detail-plan source is connected.")
    # Hög alignment = FÅ motsägelser bland de granskade.
    return 1.0 - (c["count"] / granskade), {
        "regions_examined": c["regions_examined"],
        "regions_with_real_data": granskade,
        "contradictions": c["count"], "threshold": c["threshold"],
    }, ""


def _attention_rows(market: str) -> list[dict]:
    """Bygg raderna ur det som FAKTISKT är skördat.

    Anmält kommer ur Kolada (kvot per 100k), publicerat ur nyhetsposterna
    per region, befolkningen ur den skördade befolkningssignalen. En rad
    utan alla tre tas inte med — attention_index vägrar ändå att blanda
    en kvot med ett antal, men att skicka in halva rader hade gjort dess
    vägran till en gissning om vad som saknades.
    """
    from engine import harvest, news as N
    from engine.markets import MARKETS

    if market not in MARKETS:
        return []
    anmalt, folk = {}, {}
    for r in harvest.all_rows():
        if r.get("market") not in ("", market):
            continue
        if r.get("signal_id") == "crime_index":
            anmalt[r["region_code"]] = r.get("value")
        elif r.get("signal_id") == "population_total":
            folk[r["region_code"]] = r.get("value")
    publicerat: dict[str, int] = {}
    for post in N.all_items(market=market, max_age_days=N_WINDOW_DAYS):
        kod = post.get("region_code")
        if kod:
            publicerat[kod] = publicerat.get(kod, 0) + 1
    ut = []
    for kod, kvot in anmalt.items():
        if kod not in folk:
            continue
        ut.append({"region": kod, "reported_per_100k": kvot,
                   "published": publicerat.get(kod, 0),
                   "population": folk[kod]})
    return ut


def _event_coverage_ratio(market: str, rows: list) -> tuple[float | None,
                                                            dict, str]:
    from engine.news import attention_index

    rows = rows or _attention_rows(market)
    if not rows:
        return None, {"places": 0}, (
            "No place had a reported RATE, a population and a published "
            "count together. The ratio needs all three: reported per 100k "
            "against articles per 100k. One side alone is not a ratio, and "
            "a raw count against a rate would measure population.")
    r = attention_index(rows)
    if not r["count"]:
        return None, {"places": len(rows), "peers": r["peers"]}, \
            r.get("refusal_en", "")
    # Nära medianen = rapporteringen följer incidensen. Långt ifrån åt
    # något håll drar ner — både tystnad och överdrift är avvikelser.
    avvik = [abs(x["vs_peer_median"] - 1.0) for x in r["rows"]]
    snitt = sum(avvik) / len(avvik)
    return max(0.0, 1.0 - snitt), {
        "places": r["count"], "peer_median": r["peer_median"],
        "furthest_from_median": r["rows"][0]["region"] if r["rows"] else "",
    }, ""


# Fönstret för rapportering som räknas som aktuell.
N_WINDOW_DAYS = 7.0


def mrai(market: str, *, limit: int = 0,
         attention_rows: list | None = None) -> dict:
    """Indexet för EN marknad — eller ett besked om varför det inte finns."""
    from engine.markets import MARKETS

    if market not in MARKETS:
        raise ValueError(f"Unknown market: {market}. "
                         f"Available: {', '.join(sorted(MARKETS))}")

    tackning, tbasis = _reference_coverage(market)
    grind = _component("reference_coverage", tackning, tbasis)

    if tackning < MIN_REFERENCE_COVERAGE:
        return {
            "market": market,
            "market_label_en": MARKETS[market].label_en,
            "status": "insufficient",
            "index": None,
            "components": [grind],
            "gate": {
                "reference_coverage": tackning,
                "required": MIN_REFERENCE_COVERAGE,
                "missing": tbasis["what_would_change_it"],
            },
            "refusal_en": (
                f"No index is computed for {MARKETS[market].label_en}. We "
                f"can see {_pct(tackning)}% of the signal picture here, "
                f"below the {_pct(MIN_REFERENCE_COVERAGE)}% floor — so a "
                f"low score would measure OUR blindness and be read as "
                f"this country's press. There is no honest number to give, "
                f"and giving one anyway is the single way this index does "
                f"real harm."),
            "how_to_fix_en": (
                "Connect a reference source for this market and harvest "
                "it. /v1/coverage names which ones would open how many "
                "signals."),
            **_doctrine(),
        }

    delar = [grind]
    for cid, fn in (("source_diversity", lambda: _source_diversity(market)),
                    ("independent_verification",
                     lambda: _independent_verification(market)),
                    ("public_data_alignment",
                     lambda: _public_data_alignment(market, limit)),
                    ("event_coverage_ratio",
                     lambda: _event_coverage_ratio(market,
                                                   attention_rows or []))):
        varde, basis, vagran = fn()
        delar.append(_component(cid, varde, basis, vagran))

    raknade = [d for d in delar if d["status"] == "computed" and d["weight"]]
    vikt = sum(d["weight"] for d in raknade)
    index = (round(sum(d["value"] * d["weight"] for d in raknade) / vikt, 1)
             if vikt >= MIN_WEIGHT_COMPUTED else None)
    saknade = [d["id"] for d in delar
               if d["status"] == "refused" and d["weight"]]

    return {
        "market": market, "market_label_en": MARKETS[market].label_en,
        "status": "computed" if index is not None else "insufficient",
        "index": index,
        "of_weight": round(vikt, 2),
        "components": delar,
        "refused_components": saknade,
        "refusal_en": (
            f"Components carrying {round(vikt * 100)}% of the intended "
            f"weight could be computed — below the "
            f"{round(MIN_WEIGHT_COMPUTED * 100)}% floor. The parts are "
            f"shown; no combined number is given, because a score built "
            f"from a quarter of itself looks exactly like one built from "
            f"all of it."
            if index is None and vikt else ""),
        "uncertainty_en": (
            f"Built from {len(raknade)} of {len(COMPONENTS) - 1} scoring "
            f"components, carrying {round(vikt * 100)}% of the intended "
            f"weight. The missing ones are listed rather than averaged "
            f"away — an index that silently reweights when a component is "
            f"absent hides how much of it is actually there."
            if raknade else
            "No scoring component could be computed."),
        **_doctrine(),
    }


def _doctrine() -> dict:
    return {
        "means_en": (
            "How well reporting lines up with independently verifiable "
            "records — not whether it is true, and not whether it is "
            "fair. Every component can be opened: what it rests on, how "
            "many sources, and what it cannot settle."),
        "cannot_en": (
            "It cannot rank press freedom, and must not be read as doing "
            "so. Low alignment can mean the reporting diverges, or that "
            "the official record is poor, or that our own reference data "
            "is thin — and the index cannot tell those apart. That is why "
            "a country below the coverage floor gets NO value instead of "
            "a bad one."),
        "weights_en": (
            "The weights are a documented heuristic, not a derived truth. "
            "They are data in engine/mrai.COMPONENTS so that someone who "
            "disagrees can point at the row."),
    }


def compare(markets: list[str] | None = None, **kw) -> dict:
    """Indexet för flera marknader — med de vägrade kvar i listan.

    Att tyst utelämna länderna utan index vore att låta en ranking se
    fullständig ut. De står med, utan värde, med sitt skäl.
    """
    from engine.markets import MARKETS

    ids = [m.lower() for m in (markets or sorted(MARKETS)) if m in MARKETS]
    rader = [mrai(m, **kw) for m in ids]
    med = [r for r in rader if r["index"] is not None]
    return {
        "ranked": sorted(med, key=lambda r: -r["index"]),
        "insufficient": [{"market": r["market"],
                          "market_label_en": r["market_label_en"],
                          "refusal_en": r["refusal_en"]}
                         for r in rader if r["index"] is None],
        "count": len(rader), "with_index": len(med),
        "summary_en": (
            f"{len(med)} of {len(rader)} market(s) had enough reference "
            f"coverage to be scored at all. The rest are listed WITHOUT a "
            f"value — a ranking that quietly drops what it cannot measure "
            f"looks complete and is not."),
        **_doctrine(),
    }


def catalog() -> dict:
    return {
        "components": [{k: v for k, v in c.items()} for c in COMPONENTS],
        "min_reference_coverage": MIN_REFERENCE_COVERAGE,
        "min_networks": MIN_NETWORKS,
        "window_days": N_WINDOW_DAYS,
        "scale_en": "0–100. 100 = reporting lines up closely with the "
                    "independently verifiable record we can see.",
        **_doctrine(),
    }
