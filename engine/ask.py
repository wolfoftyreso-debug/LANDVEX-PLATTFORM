"""Ask Landvex – natural language in, engine data out.

The platform's landing page: the user types as in a chat
("What are the five biggest business opportunities in Örebro right
now?") and gets answers built on the engines – never on free text
generation.

Two deliberately separated layers:

  1. INTERPRETATION (this module): deterministic, rule-based parser –
     English first, Swedish keywords kept as synonyms – extracting
     intent + entities (municipality, occupation, industry, count,
     time horizon). Testable offline, no dependencies. Can be
     replaced/augmented in the production phase by an LLM layer in
     api/ (never in the core, principle 2) producing the same Query
     objects.
  2. ANSWERS: routing to the existing engines (scan, workforce, risk,
     scoring). Every fact in the answer comes from them, with the
     same confidence, intervals, assumptions and caveats the engines
     carry.

The system does not answer "where are the jobs today?" but "where do
the needs arise before everyone else sees them?" – and always
reports how certain the conclusion is.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .datasources.base import Resolver
from .gaps import gap_analysis
from .installed_base import service_analysis, service_demand_map
from .markets import DEFAULT_MARKET, MARKETS, get_market
from .plan import establishment_plan
from .models import Location
from .profile import BusinessProfile
from .risk import assess
from .scan import economy_scenario, scan
from .segments import segment_analysis, segment_map
from .scoring import analyze
from .verticals import VERTICALS
from .workforce import (BASE_YEAR, MAX_HORIZON_YEARS, forecast, global_map, national_map)

# ── Entity lexicons (English + Swedish synonyms → id) ────────────────

_VERTICAL_SYNONYMS: dict[str, str] = {
    # English (primary)
    "hairdresser": "frisor", "hair salon": "frisor", "barber": "frisor",
    "barbershop": "frisor",
    "electrical firm": "elektriker", "electrical company": "elektriker",
    "electrical contractor": "elektriker",
    "electrical contracting": "elektriker",
    "electrical business": "elektriker",
    "gym": "gym", "fitness center": "gym", "fitness centre": "gym",
    "training facility": "gym",
    "restaurant": "restaurang",
    "café": "cafe", "cafe": "cafe", "coffee shop": "cafe",
    "coffee bar": "cafe",
    "construction company": "bygg", "building company": "bygg",
    "construction firm": "bygg",
    "dentist": "tandlakare", "dental practice": "tandlakare",
    "dental clinic": "tandlakare",
    "car repair shop": "bilverkstad", "auto repair": "bilverkstad",
    "car workshop": "bilverkstad", "auto shop": "bilverkstad",
    "veterinarian": "veterinar", "veterinary clinic": "veterinar",
    "vet clinic": "veterinar", "animal clinic": "veterinar",
    "warehouse": "lager", "logistics": "lager",
    "plumbing company": "vvs", "plumbing firm": "vvs",
    "plumbing business": "vvs", "plumbing": "vvs",
    "preschool": "forskola", "daycare": "forskola",
    "pharmacy": "apotek",
    "optician": "optiker", "eyewear store": "optiker",
    "bakery": "bageri", "baker": "bageri",
    "grocery store": "livsmedel", "supermarket": "livsmedel",
    "grocery": "livsmedel",
    "elderly care": "aldreomsorg", "eldercare": "aldreomsorg",
    "home care": "aldreomsorg",
    "cleaning company": "stadfirma", "cleaning business": "stadfirma",
    "cleaning firm": "stadfirma",
    "painting company": "malare", "painting business": "malare",
    "painting firm": "malare",
    "charging infrastructure": "laddinfra",
    "charging operator": "laddinfra",
    "bike shop": "cykelverkstad", "bicycle repair": "cykelverkstad",
    "bike repair": "cykelverkstad",
    # Swedish (kept as synonyms)
    "frisör": "frisor", "frisörsalong": "frisor", "salong": "frisor",
    "barberare": "frisor",
    "elektrikerfirma": "elektriker", "elfirma": "elektriker",
    "träningscenter": "gym", "träningsanläggning": "gym",
    "restaurang": "restaurang", "krog": "restaurang",
    "kafé": "cafe", "fik": "cafe", "kaffebar": "cafe",
    "konditori": "cafe",
    "byggföretag": "bygg", "byggfirma": "bygg",
    "tandläkare": "tandlakare", "tandläkarpraktik": "tandlakare",
    "tandvård": "tandlakare",
    "bilverkstad": "bilverkstad", "verkstad": "bilverkstad",
    "bilverkstäder": "bilverkstad", "verkstäder": "bilverkstad",
    "veterinär": "veterinar", "veterinärklinik": "veterinar",
    "djurklinik": "veterinar",
    "lager": "lager", "logistik": "lager", "logistikcenter": "lager",
    "vvs-företag": "vvs", "vvs-firma": "vvs",
    "förskola": "forskola", "dagis": "forskola",
    "apotek": "apotek",
    "optiker": "optiker", "glasögonbutik": "optiker",
    "bageri": "bageri", "bagare": "bageri",
    "livsmedelsbutik": "livsmedel", "mataffär": "livsmedel",
    "matbutik": "livsmedel", "dagligvaruhandel": "livsmedel",
    "äldreomsorg": "aldreomsorg", "hemtjänst": "aldreomsorg",
    "äldreboende": "aldreomsorg",
    "städfirma": "stadfirma", "städbolag": "stadfirma",
    "måleri": "malare", "målarfirma": "malare",
    "laddinfrastruktur": "laddinfra", "laddoperatör": "laddinfra",
    "cykelverkstad": "cykelverkstad", "cykelaffär": "cykelverkstad",
}

# Occupation → closest matching industry (for "start X" context).
_OCC_TO_VERTICAL = {"elektriker": "elektriker", "vvs_montor": "vvs",
                    "snickare": "bygg", "malare": "malare",
                    "kock": "restaurang", "underskoterska": "aldreomsorg"}

_MARKET_SYNONYMS: dict[str, str] = {
    # English (primary)
    "sweden": "se", "swedish": "se",
    "germany": "de", "german": "de",
    "usa": "us", "us state": "us", "united states": "us",
    "america": "us", "american": "us",
    "spain": "es", "spanish": "es",
    "poland": "pl", "polish": "pl",
    "france": "fr", "french": "fr",
    "italy": "it", "italian": "it",
    "netherlands": "nl", "holland": "nl", "dutch": "nl",
    "belgium": "be", "belgian": "be",
    "austria": "at", "austrian": "at",
    "portugal": "pt", "portuguese": "pt",
    "denmark": "dk", "danish": "dk",
    "finland": "fi", "finnish": "fi",
    "norway": "no", "norwegian": "no",
    "ireland": "ie", "irish": "ie",
    "czechia": "cz", "czech republic": "cz", "czech": "cz",
    "canada": "ca", "canadian": "ca",
    "mexico": "mx", "mexican": "mx",
    "colombia": "co", "colombian": "co",
    "morocco": "ma", "moroccan": "ma",
    "nigeria": "ng", "nigerian": "ng",
    "senegal": "sn", "senegalese": "sn",
    # Swedish (kept as synonyms)
    "sverige": "se", "svensk": "se",
    "tyskland": "de", "tysk": "de",
    "amerikansk": "us", "amerika": "us", "förenta staterna": "us",
    "spanien": "es", "spansk": "es",
    "polen": "pl", "polsk": "pl",
    "frankrike": "fr", "fransk": "fr",
    "italien": "it", "italiensk": "it",
    "nederländerna": "nl", "holländsk": "nl",
    "belgien": "be", "belgisk": "be",
    "österrike": "at", "österrikisk": "at",
    "portugisisk": "pt",
    "danmark": "dk", "dansk": "dk",
    "finsk": "fi", "finländsk": "fi",
    "norge": "no", "norsk": "no",
    "irland": "ie", "irländsk": "ie",
    "tjeckien": "cz", "tjeckisk": "cz",
}
_GROUP_SYNONYMS: dict[str, str] = {
    "europe": "eu", "european": "eu", "eu": "eu",
    "world": "varlden", "worldwide": "varlden", "global": "varlden",
    "globally": "varlden", "international": "varlden",
    "internationally": "varlden",
    "europa": "eu", "europeisk": "eu",
    "världen": "varlden", "globalt": "varlden",
    "internationellt": "varlden",
    "americas": "amerika", "north america": "amerika",
    "latin america": "amerika",
    "africa": "afrika", "african": "afrika", "west africa": "afrika",
}

_OCCUPATION_SYNONYMS: dict[str, str] = {
    # English (primary)
    "electrician": "elektriker",
    "plumber": "vvs_montor", "pipefitter": "vvs_montor",
    "carpenter": "snickare",
    "concrete worker": "betongarbetare",
    "tiler": "plattsattare",
    "machine operator": "maskinforare",
    "excavator operator": "maskinforare",
    "refrigeration technician": "kyltekniker",
    "heat pump technician": "kyltekniker",
    "assistant nurse": "underskoterska",
    "childcare worker": "barnskotare",
    "chef": "kock", "cook": "kock",
    "truck driver": "lastbilsforare", "lorry driver": "lastbilsforare",
    "welder": "svetsare",
    "painter": "malare",
    "it technician": "it_tekniker",
    "architect": "arkitekt",
    "construction engineer": "ingenjor_bygg",
    "civil engineer": "ingenjor_bygg", "engineer": "ingenjor_bygg",
    "teacher": "larare",
    "preschool teacher": "forskollarare",
    "nurse": "sjukskoterska",
    "property technician": "fastighetstekniker",
    "facility technician": "fastighetstekniker",
    "operations technician": "drifttekniker",
    # Swedish (kept as synonyms)
    "elektriker": "elektriker",
    "vvs": "vvs_montor", "vvs-montör": "vvs_montor",
    "vvs-installatör": "vvs_montor", "rörmokare": "vvs_montor",
    "snickare": "snickare",
    "betongarbetare": "betongarbetare",
    "plattsättare": "plattsattare",
    "maskinförare": "maskinforare", "anläggningsförare": "maskinforare",
    "anläggningsmaskinförare": "maskinforare",
    "kyltekniker": "kyltekniker", "värmepumpstekniker": "kyltekniker",
    "undersköterska": "underskoterska",
    "barnskötare": "barnskotare",
    "kock": "kock", "kockar": "kock",
    "lastbilsförare": "lastbilsforare", "chaufför": "lastbilsforare",
    "svetsare": "svetsare",
    "målare": "malare",
    "it-tekniker": "it_tekniker", "ittekniker": "it_tekniker",
    "arkitekt": "arkitekt",
    "ingenjör": "ingenjor_bygg", "byggnadsingenjör": "ingenjor_bygg",
    "byggingenjör": "ingenjor_bygg",
    "lärare": "larare",
    "förskollärare": "forskollarare",
    "sjuksköterska": "sjukskoterska",
    "fastighetstekniker": "fastighetstekniker",
    "drifttekniker": "drifttekniker",
}

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                 "en": 1, "ett": 1, "två": 2, "tre": 3, "fyra": 4,
                 "fem": 5, "sex": 6, "sju": 7, "åtta": 8, "nio": 9,
                 "tio": 10}

_SHORTAGE_WORDS = ("shortage", "missing", "lacking", "short supply",
                   "demand", "need", "recruit", "occupation",
                   "profession", "role", "skill", "retirement",
                   "brist", "saknas", "behov", "behöv", "efterfråg",
                   "yrke", "yrkesgrupp", "kompetens", "pension",
                   "rekryter")
_START_WORDS = ("start", "open", "establish", "launch", "opportunit",
                "invest", "set up", "öppna", "etablera",
                "affärsmöjlighet", "möjligheter", "driva")
_RISK_WORDS = ("risk", "dangerous", "dare", "farligt", "vågar")
_MERIT_WORDS = ("business acumen", "best run", "well run", "perform best",
                "best performing", "does best", "excel", "affärssinne",
                "bäst skött", "presterar bäst", "framgångsrik")
_SATURATION_WORDS = ("saturated", "saturation", "how crowded", "crowded",
                     "oversupplied", "market density", "mättad", "mättnad",
                     "överetablerad", "overetablerad", "trängsel")
_GAP_WORDS = ("imbalance", "underserved", "untapped", "unmet", "gap",
              "obalans", "outnyttjad", "underförsörjd",
              "underetablerad", "lucka", "vita fläckar", "white spot")
_SEGMENT_SYNONYMS: dict[str, str] = {
    # English (primary)
    "pet owner": "djuragare", "dog owner": "djuragare",
    "cat owner": "djuragare",
    "families with children": "barnfamiljer",
    "family with children": "barnfamiljer",
    "senior": "seniorer", "retiree": "seniorer",
    "pensioner": "seniorer", "elderly": "seniorer",
    "young adult": "unga_vuxna",
    "car owner": "bilagare",
    "commuter": "pendlare",
    "homeowner": "villaagare", "house owner": "villaagare",
    "high-income": "hoginkomsttagare", "high income": "hoginkomsttagare",
    "high earner": "hoginkomsttagare",
    "business owner": "foretagare", "entrepreneur": "foretagare",
    "tourist": "besokare", "visitor": "besokare",
    # Swedish (kept as synonyms)
    "djurägare": "djuragare", "hundägare": "djuragare",
    "kattägare": "djuragare", "husdjur": "djuragare",
    "barnfamilj": "barnfamiljer",
    "seniorer": "seniorer", "pensionär": "seniorer", "äldre": "seniorer",
    "unga vuxna": "unga_vuxna",
    "bilägare": "bilagare",
    "pendlare": "pendlare",
    "villaägare": "villaagare",
    "höginkomsttagare": "hoginkomsttagare",
    "företagare": "foretagare",
    "turister": "besokare", "besökare": "besokare",
}
_PRODUCT_SYNONYMS: dict[str, str] = {
    # English (primary)
    "heat pump": "varmepump_luft",
    "air source heat pump": "varmepump_luft",
    "air-source heat pump": "varmepump_luft",
    "ground source heat pump": "varmepump_berg",
    "geothermal": "varmepump_berg",
    "solar panel": "solcellsanlaggning",
    "solar cell": "solcellsanlaggning",
    "solar installation": "solcellsanlaggning",
    "pv system": "solcellsanlaggning",
    "ev charger": "laddbox", "charging box": "laddbox",
    "charging station": "laddbox", "charging point": "laddbox",
    "wallbox": "laddbox",
    "elevator": "hiss",
    "industrial robot": "industrirobot", "robot": "industrirobot",
    "ventilation": "ventilation", "ftx": "ventilation",
    "passenger car": "personbil",
    "tractor": "jordbruksmaskin",
    "agricultural machine": "jordbruksmaskin",
    "farm machinery": "jordbruksmaskin",
    "excavator": "byggmaskin", "construction machine": "byggmaskin",
    "medical technology": "medicinteknik", "x-ray": "medicinteknik",
    "server room": "it_infrastruktur", "data center": "it_infrastruktur",
    "it infrastructure": "it_infrastruktur",
    "service demand": "*",   # generic service question, no product
    "service need": "*",
    # Swedish (kept as synonyms)
    "värmepump": "varmepump_luft", "luftvärmepump": "varmepump_luft",
    "bergvärme": "varmepump_berg", "bergvärmepump": "varmepump_berg",
    "solcell": "solcellsanlaggning", "solpanel": "solcellsanlaggning",
    "solcellsanläggning": "solcellsanlaggning",
    "laddbox": "laddbox", "laddstation": "laddbox",
    "laddstolpe": "laddbox",
    "hiss": "hiss",
    "industrirobot": "industrirobot",
    "personbil": "personbil",
    "traktor": "jordbruksmaskin", "jordbruksmaskin": "jordbruksmaskin",
    "grävmaskin": "byggmaskin", "byggmaskin": "byggmaskin",
    "medicinteknik": "medicinteknik", "röntgen": "medicinteknik",
    "serverrum": "it_infrastruktur", "serverhall": "it_infrastruktur",
    "it-infrastruktur": "it_infrastruktur",
    "servicebehov": "*",
}
_PLAN_WORDS = ("establishment plan", "business plan", "create a plan",
               "make a plan", "how do i start",
               "what does it take to start",
               "etableringsplan", "affärsplan", "hur startar jag",
               "vad krävs för att starta", "beslutsunderlag")
_SEGMENT_CONTEXT = ("target group", "audience", "customer", "segment",
                    "målgrupp")
_SERVICE_CONTEXT = ("servic", "replacement", "installed base",
                    "maintenance", "spare part", "servar", "utbyte",
                    "underhåll", "installerad", "reservdel")
_MOVE_WORDS = ("move to", "relocat", "emigrat", "flytta")

# English exonyms for cities whose local/Swedish label differs.
# Pairs are matched in both directions, so parsing keeps working
# whichever language the market catalog labels happen to use.
_CITY_EXONYMS = (
    ("gothenburg", "göteborg"), ("copenhagen", "köpenhamn"),
    ("aarhus", "århus"), ("munich", "münchen"), ("cologne", "köln"),
    ("nuremberg", "nürnberg"), ("vienna", "wien"),
    ("brussels", "bryssel"), ("bruges", "brygge"),
    ("antwerp", "antwerpen"), ("ghent", "gent"),
    ("the hague", "haag"), ("hague", "haag"),
    ("rome", "rom"), ("naples", "neapel"), ("milan", "milano"),
    ("florence", "florens"), ("genoa", "genua"),
    ("venice", "venedig"),
    ("prague", "prag"), ("pilsen", "plzen"),
    ("warsaw", "warszawa"),
    ("lisbon", "lissabon"),
    ("helsinki", "helsingfors"), ("espoo", "esbo"),
    ("tampere", "tammerfors"), ("vantaa", "vanda"),
    ("turku", "åbo"), ("oulu", "uleåborg"),
    ("seville", "sevilla"),
)


@dataclass
class Query:
    intent: str
    kommun: tuple | None = None            # (code, name, lat, lon)
    segment_id: str | None = None
    product_id: str | None = None
    region_market: str = DEFAULT_MARKET              # market the region belongs to
    market: str | None = None              # explicitly mentioned market
    group: str | None = None               # "eu" | "varlden"
    occupation_id: str | None = None
    vertical_id: str | None = None
    top_n: int = 5
    target_year: int = 2035
    unmatched_kommun: str | None = None
    raw: str = ""
    tokens: list = field(default_factory=list)


# Diacritics folding. Swedish å/ä/ö are kept – they are part of the
# municipality lexicon – while other marks fold so "Munich"/"München"
# or "Krakow"/"Kraków" normalize identically on both sides.
_FOLD_MAP = str.maketrans({
    "é": "e", "è": "e", "ê": "e", "ë": "e", "ě": "e", "ę": "e",
    "á": "a", "à": "a", "â": "a", "ã": "a", "ą": "a",
    "ó": "o", "ô": "o", "õ": "o", "ø": "o",
    "í": "i", "î": "i",
    "ú": "u", "û": "u", "ü": "u", "ů": "u",
    "ñ": "n", "ń": "n", "ň": "n",
    "ç": "c", "č": "c", "ć": "c",
    "ł": "l", "ř": "r", "ś": "s", "š": "s", "ż": "z", "ź": "z",
})


def _fold(s: str) -> str:
    return s.lower().translate(_FOLD_MAP)


# Diakritvikning: de flesta skriver "Orebro", "Malmo", "Zurich" och
# "Genf/Geneve" utan tecken – särskilt på ett engelskt tangentbord. Utan
# den här mappningen matchar en helt korrekt fråga ingen region alls.
_ASCII_MAP = str.maketrans({
    "å": "a", "ä": "a", "á": "a", "à": "a", "â": "a", "ã": "a",
    "ö": "o", "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ø": "o",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ç": "c", "ñ": "n", "ß": "ss", "ł": "l", "ř": "r", "š": "s",
    "ž": "z", "č": "c", "ě": "e", "ů": "u", "ý": "y", "ą": "a",
    "ę": "e", "ś": "s", "ć": "c", "ń": "n", "ź": "z", "ż": "z",
})


def _ascii(s: str) -> str:
    """Diakritlös form för jämförelse – aldrig för visning."""
    return s.translate(_ASCII_MAP)


def _region_names(folded_label: str) -> list[str]:
    names = [folded_label]
    for a, b in _CITY_EXONYMS:
        if folded_label == _fold(b):
            names.append(_fold(a))
        elif folded_label == _fold(a):
            names.append(_fold(b))
    # Skrivet utan diakriter ska träffa lika bra som med.
    names += [_ascii(n) for n in list(names)]
    return list(dict.fromkeys(names))


def _find_region(q: str) -> tuple[str, tuple] | None:
    """Search all markets for a region name. Returns (market_id, region).

    Jämför både som skrivet och diakritlöst, så "Orebro" hittar Örebro.
    """
    qa = _ascii(q)
    for m in MARKETS.values():
        for r in m.regions:
            for name in _region_names(_fold(r[1])):
                pat = rf"\b{re.escape(name)}s?\b"
                if re.search(pat, q) or re.search(pat, qa):
                    return m.id, r
    return None


# Ord som följer "in/i" utan att vara en plats – får aldrig tolkas som en
# okänd ort (annars vägrar motorn svara på fullt begripliga frågor).
_NOT_A_PLACE = {
    "the", "a", "an", "this", "that", "these", "those", "my", "our", "your",
    "which", "what", "where", "general", "total", "particular", "fact",
    "order", "terms", "need", "demand", "shortage", "risk", "future",
    "europe", "america", "africa", "asia", "world", "eu", "us", "usa",
    "sweden", "denmark", "norway", "finland", "germany", "france", "spain",
    "italy", "poland", "canada", "mexico", "morocco", "nigeria", "senegal",
    "min", "vilken", "vilket", "vad", "var", "framtiden", "branschen",
    "sverige", "europa", "varlden", "landet", "staden", "kommunen",
}


def _find_unmatched_kommun(q: str, raw: str = "") -> str | None:
    """En ort som frågan pekar ut men systemet inte täcker.

    Fångar både det uttalade fallet ("in X municipality") och det farliga:
    ett bart ortsnamn ("in Leningrad") som INTE matchade någon region i
    någon marknad. Utan det senare faller frågan igenom till standard-
    marknaden och besvaras för fel världsdel – ett svar om Dallas på en
    fråga om Leningrad. Hellre säga "den orten täcks inte" än svara om en
    annan plats.

    Egennamn känns igen på versalen i originalfrågan (`raw`), vilket håller
    vanliga ord borta; `_NOT_A_PLACE` fångar resten.
    """
    m = re.search(r"\bin\s+([a-zåäö]+?)s?\s+municipality\b", q)
    if not m:
        m = re.search(r"\bi\s+([a-zåäö]+?)s?\s+kommun\b", q)
    if m:
        return m.group(1).capitalize()
    if not raw:
        return None
    # Versalt ord efter "in/i" som inte matchat någon känd geografi.
    for cand in re.findall(r"\b(?:in|i)\s+([A-ZÅÄÖ][\wÀ-ÿ'’\-]{2,})", raw):
        if _fold(cand).strip("'’-") in _NOT_A_PLACE:
            continue
        return cand
    return None


def _find_in_lexicon(q: str, lexicon: dict[str, str]) -> str | None:
    hits = []
    for syn, vid in lexicon.items():
        base = _fold(syn)
        stems = [base]
        if base.endswith("a"):              # sjuksköterska → sjuksköterskor
            stems.append(base[:-1])
        if base.endswith("es") and len(base) > 5:    # branches → branch
            stems.append(base[:-2])
        elif base.endswith("s") and len(base) > 4:   # chargers → charger
            stems.append(base[:-1])
        if any(re.search(rf"\b{re.escape(s)}\w*", q) for s in stems):
            hits.append((len(syn), syn, vid))
    return max(hits)[2] if hits else None   # longest synonym wins


_SUPERLATIVES = ("biggest|best|largest|greatest|top|hottest|most|"
                 "största|bästa|viktigaste|hetaste")


def _find_top_n(q: str) -> int:
    m = re.search(r"\b(\d{1,2})\b(?!\s*(år|year|km|min))", q)
    if m and 1 <= int(m.group(1)) <= 20:
        return int(m.group(1))
    for word, n in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b\s+(?:{_SUPERLATIVES})", q):
            return n
        if re.search(rf"\btop\s+{word}\b", q):       # "top five"
            return n
    return 5


def _find_year(q: str) -> int:
    m = re.search(r"\b(20[2-4]\d)\b", q)             # "by 2035"
    if m:
        return max(BASE_YEAR + 1,
                   min(BASE_YEAR + MAX_HORIZON_YEARS, int(m.group(1))))
    m = re.search(r"(?:next|coming|following|within|kommande|närmaste|"
                  r"nästa|inom)\s+(\d{1,2}|" + "|".join(_NUMBER_WORDS)
                  + r")\s+(?:years?|åren?)", q)
    if m:
        n = m.group(1)
        years = int(n) if n.isdigit() else _NUMBER_WORDS[n]
        return BASE_YEAR + max(1, min(MAX_HORIZON_YEARS, years))
    return 2035


def parse(question: str) -> Query:
    q = _fold(question.strip())
    hit = _find_region(q)
    region_market, kommun = hit if hit else ("se", None)
    occ = _find_in_lexicon(q, _OCCUPATION_SYNONYMS)
    vert = _find_in_lexicon(q, _VERTICAL_SYNONYMS)
    market = _find_in_lexicon(q, _MARKET_SYNONYMS)
    group = _find_in_lexicon(q, _GROUP_SYNONYMS)
    start = any(w in q for w in _START_WORDS)
    risky = any(w in q for w in _RISK_WORDS)
    move = any(w in q for w in _MOVE_WORDS)
    saturated = any(w in q for w in _SATURATION_WORDS)
    meritous = any(w in q for w in _MERIT_WORDS)
    # Occupation in "start/open" context → the corresponding industry.
    # I en mättnadsfråga syftar yrkesordet på BRANSCHEN: "hur mättad är
    # marknaden för elektriker" handlar om elfirmorna, inte om yrket.
    if occ and vert is None and (start or risky or saturated) \
            and occ in _OCC_TO_VERTICAL:
        vert, occ = _OCC_TO_VERTICAL[occ], None
    shortage = any(w in q for w in _SHORTAGE_WORDS)
    # Hits in both lexicons ("plumbing company"): start context →
    # industry, shortage context → occupation.
    if occ and vert:
        if start and not shortage:
            occ = None
        elif shortage and not start:
            vert = None

    query = Query(intent="hjalp", kommun=kommun, region_market=region_market,
                  market=market, group=group,
                  occupation_id=occ, vertical_id=vert,
                  top_n=_find_top_n(q), target_year=_find_year(q),
                  unmatched_kommun=None if (kommun or market or group)
                  else _find_unmatched_kommun(q, question),
                  raw=question)

    gap = any(w in q for w in _GAP_WORDS)
    plan = any(w in q for w in _PLAN_WORDS)
    segment = _find_in_lexicon(q, _SEGMENT_SYNONYMS)
    # Industry wins over segment in an establishment context
    # ("start an elderly care business" ≠ the seniors segment).
    if segment and vert and start:
        segment = None
    malgrupp = any(w in q for w in _SEGMENT_CONTEXT)
    query.segment_id = segment
    product = _find_in_lexicon(q, _PRODUCT_SYNONYMS)
    service_ctx = any(w in q for w in _SERVICE_CONTEXT)
    query.product_id = None if product == "*" else product

    if kommun is None and query.unmatched_kommun:
        query.intent = "okand_kommun"
    elif saturated and vert and kommun:
        query.intent = "marknadsmattnad"
    elif meritous:
        query.intent = "merit"
    elif plan and vert and kommun:
        query.intent = "etableringsplan"
    elif gap and vert:
        query.intent = "gap_analys"
    elif (query.product_id or product == "*" or service_ctx) \
            and kommun and not occ:
        query.intent = "servicebehov_kommun"
    elif query.product_id and not occ:
        query.intent = "service_karta"
    elif (segment or malgrupp) and kommun:
        query.intent = "malgrupper_kommun"
    elif segment:
        query.intent = "segment_karta"
    elif risky and vert and kommun:
        query.intent = "riskprofil"
    elif occ and move:
        query.intent = "land_ranking"
    elif occ and group:
        query.intent = "global_brist"
    elif occ and not kommun and (shortage or q.startswith(("var", "where"))
                                 or "var " in q or "where" in q):
        query.intent = "nationell_brist"
    elif kommun and (shortage or occ) and not start:
        query.intent = "bristyrken_kommun"
    elif vert and not kommun and start:
        query.intent = "basta_lage_vertikal"
    elif kommun and (start or vert):
        query.intent = "mojligheter_kommun"
    return query


# ── Answer builders per intent ───────────────────────────────────────

_HELP = {
    "svar_en": "I understand questions about business opportunities, "
               "skills shortages and risk – tied to a region, an "
               "occupation, an industry or a country (Sweden, Germany, "
               "the USA, Spain, Poland, France).",
    "forslag_en": [
        "What are the five biggest business opportunities in Örebro "
        "right now?",
        "Where is the imbalance greatest for car repair shops?",
        "Create an establishment plan for a car repair shop in "
        "Skellefteå.",
        "Where in Europe is the shortage of electricians greatest?",
        "How risky is it to start a gym in Solna?",
    ],
}


def _rows_merit(query: Query, resolver) -> dict:
    from .merit_scan import market_merit, region_merit
    mkt = query.market or query.region_market or DEFAULT_MARKET
    if query.kommun:
        m = region_merit(query.kommun[1], market=mkt, resolver=resolver)
        if m["status"] != "assessed":
            return {"rader": [], "svar_en": m["reason_en"], "caveats_en": []}
        return {"rader": [{"typ": "merit", "id": m["region_code"],
                           "label_en": m["region"], "score": m["overall"],
                           "detalj": {"how_en": m["how_en"],
                                      "why_en": m["why_en"],
                                      "leads_on": m["leads_on"],
                                      "drivers": m["drivers"]}}],
                "svar_en": f"{m['how_en']} {m['why_en']}",
                "caveats_en": [m["same_standard_en"]]}
    res = market_merit(mkt, top_n=query.top_n or 10, resolver=resolver)
    rows = [{"typ": "merit", "id": m["region_code"], "label_en": m["region"],
             "score": m["overall"],
             "detalj": {"rank": m["rank"], "how_en": m["how_en"],
                        "why_en": m["why_en"], "leads_on": m["leads_on"],
                        "drivers": m["drivers"]}} for m in res["ranking"]]
    top = res["ranking"][0] if res["ranking"] else None
    svar = (f"Measured across {res['assessed']} places in "
            f"{res['market_label_en']}, {top['region']} performs strongest "
            f"({top['overall']}/100). {top['how_en']}") if top else \
        "No place had enough coverage to be assessed."
    return {"rader": rows, "svar_en": svar,
            "caveats_en": [res["note_en"]]}


def _rows_mattnad(query: Query, resolver) -> dict:
    from .saturation_scan import market_saturation
    mkt = query.market or query.region_market or DEFAULT_MARKET
    res = market_saturation(query.vertical_id, query.kommun[1], market=mkt,
                            resolver=resolver)
    if res["status"] != "assessed":
        return {"rader": [], "svar_en": res["verdict_en"],
                "caveats_en": [c for c in [res.get("caveat_en")] if c]}
    caveats = [res["caveat_en"]]
    if not res["supply"]["measured"]:
        # Aldrig presentera en uppskattning som en registeruppgift.
        caveats.insert(0, "The establishment count is an ESTIMATE derived "
                          "from local signals, not a register figure. Connect "
                          "the business register (LANDVEX_REGISTER_URL) to "
                          "make it real.")
    return {
        "rader": [{"typ": "marknadsmattnad", "id": res["region_code"],
                   "label_en": res["region"], "score": res["percentile"],
                   "band": res["band"],
                   "detalj": {
                       "establishments": res["supply"]["establishments"],
                       "measured": res["supply"]["measured"],
                       "density_per_10k": res["density_per_10k"],
                       "peer_median_density": res["peer_median_density"],
                       "peers_compared": res["peers_compared"],
                       "to_reach_peer_median": res["to_reach_peer_median"],
                       "industry_code": res["industry_code"],
                       "register": res["register"],
                       "demand_reading_en": res.get("demand_reading_en"),
                       "basis_en": res["supply"]["basis_en"]}}],
        "svar_en": res["verdict_en"], "caveats_en": caveats}


def _rows_mojligheter(query: Query, resolver) -> dict[str, Any]:
    kod, namn, lat, lon = query.kommun
    mkt = get_market(query.region_market)
    loc = Location(lat, lon, address=namn)
    verts = ([query.vertical_id] if query.vertical_id
             else [v for v in VERTICALS if v != "generisk"])
    rows = []
    for vid in verts:
        r = analyze(loc, vid, resolver=resolver)
        rp = assess(loc, vid, resolver=resolver)
        eko = (economy_scenario(BusinessProfile(vertical_id=vid, team_size="2-5"),
                                r.opportunity_score)
               if mkt.calibrated else
               {"status": "ej_kalibrerad",
                "notis_en": f"Economy rules of thumb are not calibrated "
                            f"for {mkt.label_en} yet."})
        rows.append({
            "typ": "affarsmojlighet", "id": vid,
            "label_en": VERTICALS[vid].label_en,
            "score": r.opportunity_score,
            "trend": ("rising" if any(f.id == "tillvaxt" and f.score >= 60
                                      for f in r.factors) else "stable"),
            "detalj": {
                "risk_total": rp["total_risk"], "risk_band": rp["band"],
                "faktorer": [{"label_en": f.label_en, "score": f.score,
                              "narrativ_en": f.narrative_en} for f in r.factors],
                "insikter_en": r.insights_en,
                "ekonomi_schablon": eko,
                "data_coverage": r.data_coverage,
            }})
    rows.sort(key=lambda x: -x["score"])
    rows = rows[:query.top_n]
    topp = rows[0]
    return {
        "svar_en": f"Biggest business opportunities in {namn} right now – "
                   f"strongest is {topp['label_en'].lower()} "
                   f"({int(topp['score'])}/100).",
        "rader": rows,
        "forslag_en": [f"Which occupations are missing most in {namn}?",
                       f"How risky is it to start "
                       f"{topp['label_en'].lower()} in {namn}?"],
    }


def _rows_bristyrken(query: Query, resolver) -> dict[str, Any]:
    kod, namn, *_ = query.kommun
    occ_ids = [query.occupation_id] if query.occupation_id else None
    res = forecast(kod, query.target_year, occ_ids, resolver=resolver,
                   market=query.region_market)
    rows = [{
        "typ": "bristyrke", "id": f["occupation_id"], "label_en": f["label_en"],
        "score": min(100, round(100 * f["brist"] / max(f["behov_prognos"], 1) * 4)),
        "brist": f["brist"], "efterfragan": f["efterfragan"],
        "trend": f["trend"],
        "detalj": {
            "behov_nu": f["behov_nu"], "behov_prognos": f["behov_prognos"],
            "intervall": f["intervall"], "konfidens": f["konfidens"],
            "pensionsavgangar": f["pensionsavgangar"],
            "medellon_tkr_manad": f["medellon_tkr_manad"],
            "automationsrisk_schablon": f["automationsrisk_schablon"],
            "drivare": f["drivare"], "antaganden": f["antaganden"],
        }} for f in res["prognoser"] if f["brist"] > 0][:query.top_n]
    if not rows:
        return {"svar_en": f"The model sees no calculated skills shortage "
                           f"in {namn} by {query.target_year}.", "rader": []}
    return {
        "svar_en": f"Occupations with the largest calculated shortage in "
                   f"{namn} by {query.target_year}:",
        "rader": rows,
        "forslag_en": [f"Where in Sweden is the need for "
                       f"{rows[0]['label_en'].lower()} greatest?",
                       f"What are the biggest business opportunities "
                       f"in {namn}?"],
    }


def _rows_nationell(query: Query, resolver) -> dict[str, Any]:
    market = query.market or DEFAULT_MARKET
    res = national_map(query.occupation_id, query.target_year,
                       resolver=resolver, market=market)
    rows = [{
        "typ": "kommun_brist", "id": k["kommun_kod"], "label_en": k["kommun"],
        "score": min(100, round(100 * k["brist"] /
                                max(k["behov_prognos"], 1) * 4)),
        "brist": k["brist"], "efterfragan": k["efterfragan"],
        "trend": k["trend"],
        "detalj": {"behov_prognos": k["behov_prognos"],
                   "konfidens": k["konfidens"]},
    } for k in res["kommuner"][:query.top_n]]
    return {
        "svar_en": f"Largest calculated need for {res['label_en'].lower()} "
                   f"in {res['market_label_en']} by {query.target_year}: "
                   f"{', '.join(r['label_en'] for r in rows[:3])}.",
        "rader": rows,
        "karta": {"typ": "efterfragan", "kommuner": res["kommuner"],
                  "bbox": res["bbox"], "label_en": res["label_en"],
                  "malar": res["malar"]},
        "forslag_en": [f"Which occupations are missing most in "
                       f"{rows[0]['label_en']}?"],
    }


def _rows_global(query: Query, resolver) -> dict[str, Any]:
    res = global_map(query.occupation_id, query.target_year,
                     group=query.group or "eu", resolver=resolver)
    rows = [{
        "typ": "region_brist", "id": k["kommun_kod"],
        "label_en": f"{k['kommun']} ({k['market_label_en']})",
        "score": min(100, round(100 * k["brist"] /
                                max(k["behov_prognos"], 1) * 4)),
        "brist": k["brist"], "efterfragan": k["efterfragan"],
        "trend": k["trend"],
        "detalj": {"behov_prognos": k["behov_prognos"],
                   "konfidens": k["konfidens"]},
    } for k in res["regioner"][:query.top_n]]
    ranking = " · ".join(f"{r['market_label_en']} {r['snitt_brist_pct']} %"
                         for r in res["landsranking"])
    return {
        "svar_en": f"Largest calculated need for {res['label_en'].lower()} "
                   f"in {res['group_label_en']} by {query.target_year}: "
                   f"{', '.join(r['label_en'] for r in rows[:3])}. "
                   f"Average relative shortage per country: {ranking}.",
        "rader": rows,
        "karta": {"typ": "efterfragan", "kommuner": res["regioner"],
                  "bbox": res["bbox"], "label_en": res["label_en"],
                  "malar": res["malar"]},
        "forslag_en": [f"Which country is best for a Swedish "
                       f"{res['label_en'].lower()} to move to?"],
        "caveats_en": res["caveats_en"][-1:],
    }


def _rows_land_ranking(query: Query, resolver) -> dict[str, Any]:
    res = global_map(query.occupation_id, query.target_year,
                     group="varlden", resolver=resolver)
    occ_label = res["label_en"].lower()
    rows = []
    for r in res["landsranking"]:
        toppregion = next(k for k in res["regioner"]
                          if k["market"] == r["market"])
        rows.append({
            "typ": "land", "id": r["market"],
            "label_en": r["market_label_en"],
            "score": min(100, round(r["snitt_brist_pct"] * 4)),
            "trend": None,
            "detalj": {"snitt_brist_pct": r["snitt_brist_pct"],
                       "regioner_analyserade": r["regioner"],
                       "starkaste_region": f"{toppregion['kommun']} "
                                           f"(shortage {toppregion['brist']})"},
        })
    return {
        "svar_en": f"Calculated demand outlook for {occ_label} per country "
                   f"by {query.target_year} – strongest: "
                   f"{rows[0]['label_en']} (average shortage "
                   f"{rows[0]['detalj']['snitt_brist_pct']} % of need). "
                   f"Always weigh in language, licensing requirements and "
                   f"regulations – they lie outside the model.",
        "rader": rows,
        "karta": {"typ": "efterfragan", "kommuner": res["regioner"],
                  "bbox": res["bbox"], "label_en": res["label_en"],
                  "malar": res["malar"]},
        "forslag_en": [f"Where in Europe is the shortage of {occ_label} "
                       f"greatest?"],
        "caveats_en": res["caveats_en"][-1:],
    }


def _rows_basta_lage(query: Query, resolver) -> dict[str, Any]:
    res = scan(BusinessProfile(vertical_id=query.vertical_id),
               resolver=resolver, top_n=query.top_n,
               market=query.market or DEFAULT_MARKET)
    rows = [{
        "typ": "hotspot", "id": h["kommun_kod"], "label_en": h["lage_en"],
        "score": h["opportunity_score"], "trend": h["market_momentum"]["direction"],
        "detalj": {"confidence": h["confidence"], "risk_index": h["risk_index"],
                   "competition_gap": h["competition_gap"],
                   "time_window_months": h["time_window_months"],
                   "motivering_en": h["motivering_en"],
                   "ekonomi_schablon": h["economy_scenario"]},
    } for h in res["hotspots"]]
    return {
        "svar_en": f"Best locations for {res['vertical_label_en'].lower()} "
                   f"in {res['market_label_en']} – top candidate "
                   f"{rows[0]['label_en']} ({int(rows[0]['score'])}/100).",
        "rader": rows,
        "karta": {"typ": "heatmap", "heatmap": res["heatmap"],
                  "hotspots": res["hotspots"], "level": res["level"],
                  "bbox": res["bbox"]},
        "forslag_en": [f"How risky is it to start "
                       f"{res['vertical_label_en'].lower()} in "
                       f"{rows[0]['label_en'].split(',')[0]}?"],
    }


def _rows_gap(query: Query, resolver) -> dict[str, Any]:
    res = gap_analysis(query.vertical_id, market=query.market or DEFAULT_MARKET,
                       resolver=resolver, top_n=query.top_n)
    rows = [{
        "typ": "obalans", "id": e["kommun_kod"], "label_en": e["kommun"],
        "score": e["obalans_score"],
        "trend": e["utveckling_riktning"],
        "detalj": {
            "klass": e["klass"].replace("_", " "),
            "efterfragan": e["efterfragan"],
            "utbudsunderskott": e["utbudsunderskott"],
            "utveckling": e["utveckling"],
            "opportunity_score": e["opportunity_score"],
            "motivering_en": [e["narrativ_en"]] + [
                f"{r['label_en']}: {r['varde']} {r['enhet']} "
                f"({r['bedomning_en']}, source {r['kalla']})"
                for r in (e["forklaring"]["efterfragan"][:4] +
                          e["forklaring"]["utbud"])],
        }} for e in res["obalanser"]]
    return {
        "svar_en": res["sammanfattning_en"] + (
            f" Largest imbalance: {rows[0]['label_en']} "
            f"({int(rows[0]['score'])}/100)." if rows else ""),
        "rader": rows,
        "karta": {"typ": "heatmap", "heatmap": res["heatmap"],
                  "hotspots": [], "bbox": res["bbox"], "level": "oversikt"},
        "forslag_en": [f"Create an establishment plan for "
                       f"{res['vertical_label_en'].lower()} in "
                       f"{rows[0]['label_en']}." if rows else
                       "Where is the imbalance greatest for dentists?"],
        "caveats_en": res["caveats_en"],
    }


def _rows_plan(query: Query, resolver) -> dict[str, Any]:
    kod = query.kommun[0]
    p = establishment_plan(kod, query.vertical_id,
                           market=query.region_market, resolver=resolver)
    inv, eko = p["investering_tkr"], p["ekonomi"]
    rows = [
        {"typ": "plan", "id": "lokal", "label_en": "Premises",
         "score": p["opportunity_score"], "trend": None,
         "detalj": {"storlek": f"{p['lokal']['storlek_m2'][0]}–"
                               f"{p['lokal']['storlek_m2'][1]} m²",
                    "narrativ_en": p["lokal"]["hyreslage_en"]}},
        {"typ": "plan", "id": "investering",
         "label_en": f"Investment (k{p.get('currency', 'SEK')})",
         "score": inv["totalt"][1], "trend": None,
         "detalj": {"startkapital": f"{inv['startkapital'][0]}–{inv['startkapital'][1]}",
                    "utrustning": f"{inv['utrustning'][0]}–{inv['utrustning'][1]}",
                    "totalt": f"{inv['totalt'][0]}–{inv['totalt'][1]}",
                    "narrativ_en": inv["notis_en"],
                    "motivering_en": [f["alternativ_en"] + " – " + f["notis_en"]
                                      for f in p["finansiering"]]}},
        {"typ": "plan", "id": "personal", "label_en": "Staff",
         "score": p["personal"]["antal"], "trend": None,
         "detalj": {"narrativ_en": p["personal"]["notis_en"],
                    "motivering_en": [
                        f"{y['label_en']} ({y['medellon_tkr_manad']} "
                        f"k{p.get('currency', 'SEK')}/month): "
                        f"{y['rekryteringslage_en']}"
                        for y in p["personal"]["yrken"]] or
                        ["Staffing according to selected team size."]}},
        {"typ": "plan", "id": "ekonomi",
         "label_en": "Economy (rule of thumb)",
         "score": eko.get("omsattningsscenario_tkr_ar", 0), "trend": None,
         "detalj": ({"omsattning_tkr_ar": eko["omsattningsscenario_tkr_ar"],
                     "resultat_tkr_ar": f"{eko['rorelseresultat_tkr_ar'][0]}–"
                                        f"{eko['rorelseresultat_tkr_ar'][1]}",
                     "aterbetalningstid_ar":
                         (f"{eko['aterbetalningstid_ar'][0]}–"
                          f"{eko['aterbetalningstid_ar'][1]} years"
                          if eko.get("aterbetalningstid_ar") else "not computable"),
                     "narrativ_en": eko["notis_en"]}
                    if "omsattningsscenario_tkr_ar" in eko else
                    {"narrativ_en": eko["notis_en"]})},
        {"typ": "plan", "id": "risker", "label_en": "Key risks",
         "score": p["risk_total"], "trend": None,
         "detalj": {"motivering_en": [
             f"{r['label_en']} ({int(r['risk'])}/100, {r['band']})"
             + (f" – {r['atgard_en']}" if r["atgard_en"] else "")
             for r in p["risker"]]}},
    ]
    return {
        "svar_en": f"Establishment plan for {p['vertical_label_en'].lower()} "
                   f"in {p['kommun']}: score {int(p['opportunity_score'])}"
                   f"/100, total investment {inv['totalt'][0]}–"
                   f"{inv['totalt'][1]} k{p.get('currency', 'SEK')} "
                   f"(rule of thumb). Next steps: "
                   f"{' · '.join(p['nasta_steg_en'][:3])}.",
        "rader": rows,
        "forslag_en": [f"How risky is it to start "
                       f"{p['vertical_label_en'].lower()} in {p['kommun']}?"],
        "caveats_en": p["caveats_en"],
    }


def _rows_service_karta(query: Query, resolver) -> dict[str, Any]:
    res = service_demand_map(query.product_id, market=query.market or DEFAULT_MARKET,
                             resolver=resolver)
    rows = [{
        "typ": "servicebehov", "id": r["kommun_kod"], "label_en": r["kommun"],
        "score": r["utbyten_till_malar"],
        "trend": None,
        "detalj": {
            "installerad_bas": f"{r['installerad_bas']} (estimate)",
            "utbyten_till_malar": r["utbyten_till_malar"],
            "servicetillfallen_per_ar": r["servicetillfallen_per_ar"],
            "teknikerbehov": r["teknikerbehov"],
            "narrativ_en": r["teknikerlage"]["text_en"],
            "motivering_en": (["Mismatch: large installed base but "
                               "technician shortage – business "
                               "opportunity."]
                              if r["mismatch"] else []),
        }} for r in res["regioner"][:query.top_n]]
    return {
        "svar_en": res["sammanfattning_en"],
        "rader": rows,
        "karta": {"typ": "heatmap", "heatmap": res["heatmap"],
                  "hotspots": [], "bbox": res["bbox"], "level": "oversikt"},
        "forslag_en": [f"Where is the imbalance greatest for "
                       f"{res['betjanas_av']['label_en'].lower()}?"],
        "caveats_en": res["antaganden_en"],
    }


def _rows_servicebehov(query: Query, resolver) -> dict[str, Any]:
    kod = query.kommun[0]
    res = service_analysis(kod, market=query.region_market, resolver=resolver)
    prods = ([p for p in res["produkter"] if p["product_id"] == query.product_id]
             if query.product_id else res["produkter"])
    rows = [{
        "typ": "produkt", "id": p["product_id"], "label_en": p["label_en"],
        "score": p["utbyten_till_malar"], "trend": None,
        "detalj": {
            "installerad_bas": f"{p['installerad_bas']} (estimate)",
            "utbyten_till_malar": p["utbyten_till_malar"],
            "servicetillfallen_per_ar": p["servicetillfallen_per_ar"],
            "teknikerbehov": p["teknikerbehov"],
            "livslangd": f"{p['livslangd_ar']} years, service every "
                         f"{p['serviceintervall_ar']} years",
            "certifiering": p["certifiering_en"],
            "narrativ_en": p["felmonster_en"],
            "motivering_en": [p["teknikerlage"]["text_en"],
                              f"Spare parts: {p['reservdelar_en']}.",
                              f"Season: {p['sasong_en']}.",
                              f"Served by: {p['betjanas_av']['label_en']}."],
        }} for p in prods]
    return {
        "svar_en": res["sammanfattning_en"],
        "rader": rows,
        "forslag_en": [f"Where in Sweden is the service demand for "
                       f"{rows[0]['label_en'].lower()} greatest?" if rows else
                       "Which region has the most heat pumps approaching "
                       "replacement age?"],
        "caveats_en": res["antaganden_en"],
    }


def _rows_malgrupper(query: Query, resolver) -> dict[str, Any]:
    kod = query.kommun[0]
    res = segment_analysis(kod, market=query.region_market, resolver=resolver)
    seg_filter = ([query.segment_id] if query.segment_id else
                  [s["segment_id"] for s in res["segment"]])
    rows = [{
        "typ": "malgrupp", "id": s["segment_id"], "label_en": s["label_en"],
        "score": s["index_mot_marknadssnitt"], "trend": None,
        "detalj": {
            "antal_uppskattat": (f"{s['antal_uppskattat']} {s['enhet_en']}"
                                 if s["antal_uppskattat"] is not None
                                 else "index segment"),
            "index_mot_marknadssnitt": s["index_mot_marknadssnitt"],
            "narrativ_en": s["narrativ_en"],
            "motivering_en": ["Served by: " + ", ".join(
                b["label_en"] for b in s["betjanas_av"]) + "."],
        }} for s in res["segment"] if s["segment_id"] in seg_filter]
    topp = rows[0]
    return {
        "svar_en": res["sammanfattning_en"] if not query.segment_id else (
            f"{topp['label_en']} in {res['kommun']}: "
            f"{topp['detalj']['antal_uppskattat']} (estimated), index "
            f"{topp['score']} vs the market average."),
        "rader": rows,
        "forslag_en": [f"Where in Sweden are there the most "
                       f"{topp['label_en'].lower()}?",
                       f"What are the biggest business opportunities in "
                       f"{res['kommun']}?"],
        "caveats_en": res["caveats_en"],
    }


def _rows_segment_karta(query: Query, resolver) -> dict[str, Any]:
    res = segment_map(query.segment_id, market=query.market or DEFAULT_MARKET,
                      resolver=resolver)
    rows = [{
        "typ": "segment_region", "id": r["kommun_kod"],
        "label_en": r["kommun"], "score": r["index"], "trend": None,
        "detalj": {
            "antal_uppskattat": (f"{r['antal_uppskattat']} "
                                 if r["antal_uppskattat"] is not None else "–"),
            "index_mot_marknadssnitt": r["index"],
            "narrativ_en": f"Index {r['index']} vs the market average.",
        }} for r in res["regioner"][:query.top_n]]
    verts = res["betjanas_av"]
    return {
        "svar_en": res["sammanfattning_en"],
        "rader": rows,
        "karta": {"typ": "heatmap", "heatmap": res["heatmap"],
                  "hotspots": [], "bbox": res["bbox"], "level": "oversikt"},
        "forslag_en": ([f"Where is the imbalance greatest for "
                        f"{verts[0]['label_en'].lower()}?"] if verts else []),
        "caveats_en": res["caveats_en"],
    }


def _rows_risk(query: Query, resolver) -> dict[str, Any]:
    kod, namn, lat, lon = query.kommun
    rp = assess(Location(lat, lon, address=namn), query.vertical_id,
                resolver=resolver)
    rows = [{
        "typ": "riskdimension", "id": d["id"], "label_en": d["label_en"],
        "score": d["risk"], "trend": None,
        "detalj": {"band": d["band"], "narrativ_en": d["narrativ_en"],
                   "atgard_en": d["atgard_en"], "signaler": d["signaler"]},
    } for d in rp["dimensioner"]]
    return {"svar_en": rp["narrativ_en"] + f" Applies to "
                       f"{rp['vertical_label_en'].lower()} in {namn}.",
            "rader": rows,
            "forslag_en": [f"What are the biggest business opportunities "
                           f"in {namn}?"]}


def ask(question: str, resolver: Resolver | None = None) -> dict[str, Any]:
    """Main entry: natural-language question → structured engine answer."""
    if not question or not question.strip():
        return {"fraga": question, "intent": "hjalp", **_HELP,
                "rader": [], "caveats_en": []}
    query = parse(question)
    base = {"fraga": question, "intent": query.intent, "rader": [],
            "malar": query.target_year}

    if query.intent == "okand_kommun":
        se = get_market("se")
        exempel = ", ".join(r[1] for r in se.regions[:6])
        return {**base,
                # Täckningen räknas ur MARKETS, aldrig ur en handskriven
                # mening – annars åldras löftet snabbare än plattformen.
                "svar_en": f"{query.unmatched_kommun} is not covered yet. "
                           f"The platform currently answers for "
                           f"{sum(len(m.regions) for m in MARKETS.values())} "
                           f"regions across {len(MARKETS)} markets "
                           f"({', '.join(sorted(m.id.upper() for m in MARKETS.values()))}). "
                           f"Swedish examples: {exempel}. Rather than answer "
                           f"for somewhere else, the platform says a place is "
                           f"outside its coverage.",
                "caveats_en": []}
    if query.intent == "hjalp":
        return {**base, **_HELP, "caveats_en": []}

    handler = {"mojligheter_kommun": _rows_mojligheter,
               "marknadsmattnad": _rows_mattnad,
               "merit": _rows_merit,
               "bristyrken_kommun": _rows_bristyrken,
               "nationell_brist": _rows_nationell,
               "global_brist": _rows_global,
               "land_ranking": _rows_land_ranking,
               "basta_lage_vertikal": _rows_basta_lage,
               "gap_analys": _rows_gap,
               "etableringsplan": _rows_plan,
               "malgrupper_kommun": _rows_malgrupper,
               "segment_karta": _rows_segment_karta,
               "service_karta": _rows_service_karta,
               "servicebehov_kommun": _rows_servicebehov,
               "riskprofil": _rows_risk}[query.intent]
    result = handler(query, resolver)
    caveats = result.pop("caveats_en", []) + [
        "The answer is computed by the Landvex engines on the current "
        "data foundation – decision support, not a guarantee. Confidence "
        "and assumptions are reported per row."]
    return {**base, **result, "caveats_en": caveats}
