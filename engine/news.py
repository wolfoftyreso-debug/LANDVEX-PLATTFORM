"""Nyheter som underlag — med grinden FÖRE, inte efter.

Nyhetsflöden ska mata den samlade analysen, inte ligga i en egen låda.
Det är rätt beslut och det är också det farligaste: ett system som låter
en rubrik röra ett tal är en ryktesförstärkare med API. Hela den här
modulen är byggd runt den risken.

**Fyra regler, och den första är den som gör resten möjlig.**

1. **Fem tidningar med samma telegram är EN källa.** Syndikering är det
   som gör "bekräftat av flera medier" värdelöst: TT, Reuters och AP
   säljer samma text till hundra redaktioner, och den som räknar
   utgivare i stället för NÄT får hundra bekräftelser på en enda
   rapport. Vi klustrar därför på texten och räknar `owner`, inte
   `outlet`. `engine/corroboration.assess` fick i den här sessionen
   exakt det fältet.

2. **En ensam utgivare får ALDRIG röra ett tal.** Den registreras, den
   syns, den kan läsas — men `may_inform_analysis` är False. Det är
   samma tak som gäller allt annat: en källa kan inte bekräfta sig
   själv.

3. **Nyheter rör BAND, aldrig värden.** En artikel kan höja en
   riskbedömning från "låg" till "förhöjd" och namnge varför. Den får
   inte sätta `pop_growth_pct` till 2,4. Skillnaden är att ett band går
   att argumentera emot; ett tal ser ut som en mätning.

4. **Motsägelse mellan utgivare är ett fynd, inte ett medelvärde.** Två
   nät som säger emot varandra ger `conflicting` — sämre underlag än en
   ensam källa, eftersom minst en har fel och man inte vet vilken.

Formen är RSS/Atom: nyckellöst, universellt, och "alla tänkbara flöden"
är därmed en rad var i `FEEDS`.

Rent stdlib, injicerbar transport.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405 – deklarationer avvisas nedan

from engine.claims import canonical_hash
from engine.corroboration import assess

# Hur många OBEROENDE nät en uppgift måste ha för att få påverka något.
# Två är minimum av samma skäl som överallt annars i plattformen.
MIN_NETWORKS_TO_INFORM = 2

# Största dokument som parsas. En feed är kilobyte; något som är tiotals
# megabyte är inte en feed.
_MAX_BYTES = 4 << 20


# ── Utgivare och ÄGARE ──────────────────────────────────────────────────
# `owner` är det som räknas som nät. Två titlar med samma ägare är EN
# röst, hur olika de än ser ut på förstasidan. `agency` markerar rena
# telegrambyråer: publicerar tio tidningar samma byråtext är det ett nät.
#
# En ny utgivare är en rad. Fältet som ALDRIG får gissas är `owner` — en
# felaktig ägare gör syndikering till bekräftelse.
OUTLETS: dict[str, dict] = {
    "tt": {"label_en": "TT Nyhetsbyrån", "owner": "tt", "agency": True,
           "markets": ("se",)},
    "reuters": {"label_en": "Reuters", "owner": "reuters", "agency": True,
                "markets": ()},
    "ap": {"label_en": "Associated Press", "owner": "ap", "agency": True,
           "markets": ()},
    "svt": {"label_en": "SVT Nyheter", "owner": "svt", "agency": False,
            "markets": ("se",)},
    "sr": {"label_en": "Sveriges Radio Ekot", "owner": "sr", "agency": False,
           "markets": ("se",)},
    "dn": {"label_en": "Dagens Nyheter", "owner": "bonnier",
           "agency": False, "markets": ("se",)},
    "di": {"label_en": "Dagens Industri", "owner": "bonnier",
           "agency": False, "markets": ("se",)},
    "svd": {"label_en": "Svenska Dagbladet", "owner": "schibsted",
            "agency": False, "markets": ("se",)},
    "aftonbladet": {"label_en": "Aftonbladet", "owner": "schibsted",
                    "agency": False, "markets": ("se",)},
}


def outlets_are_independent(a: str, b: str) -> dict:
    """Är två utgivare oberoende röster?

    DN och Di har olika redaktioner och samma ägare. Att räkna dem som
    två bekräftelser vore att räkna en koncern som en marknad.
    """
    oa = OUTLETS.get(a, {}).get("owner", a)
    ob = OUTLETS.get(b, {}).get("owner", b)
    return {
        "a": a, "b": b, "owner_a": oa, "owner_b": ob,
        "independent": oa != ob,
        "why_en": ("Different owners, different editorial chains."
                   if oa != ob else
                   f"Same owner ({oa}). Two titles under one company are "
                   f"one voice, however different the front pages look."),
    }


# ── Flödet in ───────────────────────────────────────────────────────────
def parse_feed(raw: bytes, outlet: str) -> list[dict]:
    """RSS eller Atom → poster. Samma dokumentspärr som ENTSO-E.

    Entitetsdeklarationer avvisas oparsade: `xml.etree` expanderar dem,
    `defusedxml` är ett beroende kärnan inte får ta, och båda attackerna
    kräver en deklaration.
    """
    if len(raw) > _MAX_BYTES:
        raise ValueError(f"feed is {len(raw)} bytes, over the {_MAX_BYTES} "
                         f"limit — not parsed")
    if b"<!doctype" in raw[:4096].lower() or b"<!entity" in raw[:65536].lower():
        raise ValueError("the feed declares entities; refused unparsed")
    rot = ET.fromstring(raw.decode("utf-8", "replace"))  # noqa: S314

    def _text(el, *namn) -> str:
        for n in namn:
            for barn in el.iter():
                if barn.tag.rsplit("}", 1)[-1] == n and (barn.text or "").strip():
                    return barn.text.strip()
        return ""

    poster = []
    for el in rot.iter():
        if el.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        titel = _text(el, "title")
        if not titel:
            continue
        poster.append({
            "outlet": outlet,
            "owner": OUTLETS.get(outlet, {}).get("owner", outlet),
            "title": titel,
            "summary": _text(el, "description", "summary", "content"),
            "published": _text(el, "pubDate", "published", "updated"),
            "link": _text(el, "link", "id"),
        })
    return poster


# ── Klustring: samma uppgift, olika avsändare ───────────────────────────
_ORD = re.compile(r"[a-zà-öA-ZÀ-Ö0-9]+")
_STOPP = {"och", "att", "det", "som", "för", "med", "har", "the", "and",
          "for", "that", "with", "från", "till", "efter", "under", "says",
          "enligt", "about", "after"}


def _fingeravtryck(text: str) -> frozenset:
    """Ordmängd utan stoppord. Två telegram som skiljer sig på rubriken
    men inte på innehållet ska ändå hamna i samma kluster."""
    ord_ = [w.lower() for w in _ORD.findall(text or "")]
    return frozenset(w for w in ord_ if len(w) > 2 and w not in _STOPP)


def _likhet(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


SAME_STORY_AT = 0.45


def cluster(items: list[dict]) -> list[dict]:
    """Gruppera poster som handlar om samma sak.

    Klustret är enheten som bedöms — inte artikeln. Tio artiklar om en
    fabriksnedläggning är EN uppgift som tio redaktioner rapporterat, och
    frågan är hur många av dem som är oberoende av varandra.
    """
    kvar = list(items)
    kluster = []
    while kvar:
        frö = kvar.pop(0)
        fp = _fingeravtryck(f"{frö['title']} {frö.get('summary', '')}")
        grupp = [frö]
        rester = []
        for x in kvar:
            if _likhet(fp, _fingeravtryck(
                    f"{x['title']} {x.get('summary', '')}")) >= SAME_STORY_AT:
                grupp.append(x)
            else:
                rester.append(x)
        kvar = rester
        kluster.append(_bedom(grupp))
    return sorted(kluster, key=lambda k: -k["independent_networks"])


def _bedom(grupp: list[dict]) -> dict:
    """Trovärdigheten för EN uppgift, räknad på nät och inte på rubriker."""
    agare = sorted({g.get("owner") or g["outlet"] for g in grupp})
    byraer = sorted({g["outlet"] for g in grupp
                     if OUTLETS.get(g["outlet"], {}).get("agency")})
    # Varje ägare är ett nät. `sensor_class` är samma för alla — de mäter
    # samma sak (rapportering) — så bandet kan aldrig nå `strong`, vilket
    # är rätt: tio tidningar är fortfarande bara tidningar.
    korr = assess([{"sensor_class": "reporting", "network": a}
                   for a in agare])
    n = len(agare)
    return {
        "title": grupp[0]["title"],
        "items": grupp, "outlets": sorted({g["outlet"] for g in grupp}),
        "owners": agare, "independent_networks": n,
        "agencies": byraer,
        "strength": korr["strength"],
        "may_inform_analysis": n >= MIN_NETWORKS_TO_INFORM,
        "checksum": canonical_hash({"title": grupp[0]["title"],
                                    "owners": agare}),
        "why_en": (
            f"{len(grupp)} article(s) from {n} independent owner(s)."
            + (f" {len(byraer)} of the sources is a wire agency, so titles "
               f"carrying that copy are one voice, not several."
               if byraer else "")
            + ("" if n >= MIN_NETWORKS_TO_INFORM else
               " A single owner cannot corroborate itself: this is "
               "recorded and readable, but it may not move any "
               "assessment.")),
        "cannot_en": (
            "Agreement between outlets is agreement about a REPORT, not "
            "about the world. Ten newsrooms can repeat one wrong source, "
            "and this measure cannot see that — it can only see that they "
            "are separate companies."),
    }


# ── Vägen in i analysen ─────────────────────────────────────────────────
def claims_for(clusters: list[dict], *, market: str = "") -> dict:
    """Vad nyhetsläget FÅR bidra med till den samlade analysen.

    Bara kluster med minst två oberoende ägare släpps igenom, och de
    bidrar med ett BAND och en motivering — aldrig med ett tal.
    """
    slappt = [k for k in clusters if k["may_inform_analysis"]]
    hallet = [k for k in clusters if not k["may_inform_analysis"]]
    return {
        "market": market,
        "may_inform": [{
            "title": k["title"], "owners": k["owners"],
            "networks": k["independent_networks"],
            "strength": k["strength"], "checksum": k["checksum"],
            "contributes_en": (
                "May raise or lower a RISK BAND with the outlets named as "
                "its basis. It may never set a numeric signal: a band can "
                "be argued with, a number looks like a measurement."),
        } for k in slappt],
        "held_back": [{"title": k["title"], "owners": k["owners"],
                       "why_en": k["why_en"]} for k in hallet],
        "count": len(slappt), "held_back_count": len(hallet),
        "min_networks": MIN_NETWORKS_TO_INFORM,
        "means_en": (
            "News feeds the collected analysis through a gate, not around "
            "it. What passes carries the outlets that carry it, so a "
            "reader can go and check."),
        "cannot_en": (
            "Nothing here becomes a signal value. News moves bands and "
            "names its basis; a headline that could set a number would "
            "make this a rumour amplifier with an API."),
    }


# ── Uppmärksamhetsindexet: anmält mot publicerat ────────────────────────
# Två register om samma verklighet som inte behöver stämma överens. Det
# ena är myndighetens (anmälda brott), det andra redaktionernas
# (publicerade artiklar). Kvoten säger hur mycket uppmärksamhet en plats
# får i förhållande till sin registrerade incidens — jämfört med
# liknande platser.
#
# VAD DEN INTE MÄTER, och det är hela dess integritet:
#
#   * inte hur mycket brott som SKETT. Anmälningsbenägenheten varierar
#     kraftigt mellan brottstyper och mellan grupper; mörkertalet är
#     olika stort överallt. Kvoten är publicerat mot ANMÄLT, aldrig
#     publicerat mot inträffat.
#   * inte om någon ljuger. Låg täckning kan vara redaktionella
#     prioriteringar, avstånd till en redaktion eller att ingen sökt upp
#     platsen — och hög täckning kan vara ett enda uppmärksammat fall.
#   * inte ett omdöme om en plats. Att publicera en lista över platser
#     med "för mycket brottsrapportering" vore att göra ett mått till en
#     anklagelse.
PEER_MIN = 5          # under så här många jämförbara platser: ingen kvot


def attention_index(rows: list[dict]) -> dict:
    """Publicerat per anmält, jämfört med jämförbara platser.

    `rows` = [{"region": .., "reported": <antal anmälda>,
               "published": <antal artiklar>, "category": ..}]
    Båda talen ska komma UTIFRÅN — modulen räknar en kvot, den hämtar
    ingenting och hittar aldrig på ett av dem.
    """
    giltiga = [r for r in rows
               if isinstance(r.get("reported"), (int, float))
               and isinstance(r.get("published"), (int, float))
               and r["reported"] > 0]
    if len(giltiga) < PEER_MIN:
        return {
            "rows": [], "count": 0, "peers": len(giltiga),
            "refusal_en": (
                f"An attention ratio needs peers to mean anything: one "
                f"place's number is not high or low by itself. Fewer than "
                f"{PEER_MIN} comparable places had both a reported count "
                f"and a published count, so no ratio was computed."),
            "cannot_en": _ATT_CANNOT,
        }
    kvoter = [r["published"] / r["reported"] for r in giltiga]
    ordnat = sorted(kvoter)
    median = ordnat[len(ordnat) // 2]
    ut = []
    for r, k in zip(giltiga, kvoter, strict=True):
        rel = (k / median) if median else 0.0
        band = ("far_above" if rel >= 2.0 else "above" if rel >= 1.25
                else "below" if rel <= 0.8 else "typical")
        ut.append({
            "region": r.get("region", ""), "category": r.get("category", ""),
            "reported": r["reported"], "published": r["published"],
            "published_per_reported": round(k, 4),
            "vs_peer_median": round(rel, 2), "band": band,
            "means_en": (
                f"{r['published']} article(s) per {r['reported']} reported "
                f"incident(s) — {round(rel, 2)}× the median of "
                f"{len(giltiga)} comparable places."),
        })
    return {
        "rows": sorted(ut, key=lambda x: -x["vs_peer_median"]),
        "count": len(ut), "peers": len(giltiga),
        "peer_median": round(median, 4),
        "means_en": (
            "How much a place is written about relative to what is "
            "REPORTED there, measured against comparable places. It is an "
            "attention ratio, and attention is the only thing it "
            "measures."),
        "cannot_en": _ATT_CANNOT,
    }


_ATT_CANNOT = (
    "It does not measure how much happened. Propensity to report varies "
    "sharply between offence types and between groups, and the dark "
    "figure is a different size everywhere — this is published against "
    "REPORTED, never published against occurred. A low ratio is not proof "
    "of silence and a high one is not proof of exaggeration: one "
    "well-covered case moves it as much as a pattern does. Reading it as "
    "a verdict on a place would turn a measurement into an accusation.")


def catalog() -> dict:
    agare: dict[str, list[str]] = {}
    for oid, o in OUTLETS.items():
        agare.setdefault(o["owner"], []).append(oid)
    return {
        "outlets": [{"id": k, **v} for k, v in OUTLETS.items()],
        "owners": {k: sorted(v) for k, v in sorted(agare.items())},
        "count": len(OUTLETS),
        "min_networks_to_inform": MIN_NETWORKS_TO_INFORM,
        "same_story_at": SAME_STORY_AT,
        "attention_index": {"peer_min": PEER_MIN,
                            "cannot_en": _ATT_CANNOT},
        "principle_en": (
            "Five papers running the same wire copy are ONE source. "
            "Syndication is what makes 'confirmed by several media' "
            "worthless, so clusters are counted by OWNER and agency copy "
            "is marked. A claim needs two independent owners before it "
            "may inform any assessment."),
        "cannot_en": (
            "Agreement between outlets is agreement about a report, not "
            "about the world — ten newsrooms can repeat one wrong source. "
            "And nothing from here ever sets a numeric signal; news moves "
            "a band and names the outlets behind it."),
    }
