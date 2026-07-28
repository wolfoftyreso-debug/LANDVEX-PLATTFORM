"""Öppna källor läses in EN gång per dygn och lagras. Frågan läser lagret.

Plattformen hade ett problem som inte gick att lösa i förfrågningsvägen:
`competition_pressure` och `provider_gap` var mock i **alla 35
marknader**, eftersom `engine/datasources/places.py` väntar på att någon
ska ställa upp en egen tjänst — och ingen sådan finns. De två signalerna
bär utbudssidan i beslutskortet och 0,35 av vikten i obalansformeln.

OpenStreetMap fyller precis den luckan, nyckellöst och globalt. Men ett
marknadssvep träffar 75 regioner, svarsbudgeten är 700 ms och ett
Overpass-anrop tar sekunder. Att fråga i förfrågningsvägen hade varit
tre fel samtidigt: långsamt, ovänligt mot en gratistjänst, och
oreproducerbart — samma fråga två gånger kunde gett olika svar.

**Därför skördas det.** En gång per dygn, ett anrop per region, in i
vårt eget lager. Förfrågningsvägen (`HarvestedSource` i
`engine/datasources/adapters.py`) rör aldrig ett tredjepartsnät.

Tre regler som inte är kosmetiska:

  * **Ålder.** En rad äldre än källans `max_age_days` läses som
    FRÅNVARANDE, inte som ett värde. Ett gammalt tal som serveras tyst
    är precis det fel plattformen finns för att förhindra, och
    skillnaden mot mock måste synas i `data_coverage`.
  * **Avstånd.** En punkt matchas mot närmaste skördade region inom en
    radie. Avståndet följer med ut: en mätning från grannkommunen är ett
    svagare underlag än en från platsen.
  * **En kartlagd plats är inte ett registrerat företag.** OSM får fylla
    observerat utbud men ALDRIG etableringsräkningen i
    `/v1/saturation` — den kommer ur ett företagsregister eller vägras.

Allt är data: en ny källa är en rad i `SOURCES`, en ny bransch en rad i
`OSM_TAGS`.

Rent stdlib, injicerbar transport.
"""
from __future__ import annotations

import json
import math
import os
import time
import time as _time
import urllib.parse
import urllib.request

from engine.datasources.faults import OUR_BUGS, Breaker

_UA = "landvex-opportunity-engine/harvest"

# Radien runt en regioncentroid som räknas som "här". Samma tal som
# scan använder för sitt närområde; större radie gör en storstadssiffra
# till en landsbygdssiffra.
DEFAULT_RADIUS_M = 3000

# Hur långt ifrån en skördad region en punkt får ligga och ändå få
# svaret. 25 km är ungefär en kommun; längre bort är det en annan ort.
MATCH_RADIUS_KM = 25.0


def _http_post(url: str, payload: bytes, timeout: float) -> bytes:
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.read()


def _http_get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.read()


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Storcirkelavstånd. Samma formel som scb._haversine_km — men den
    ligger i en SE-specifik modul och skördelagret är globalt."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


# ── Bransch → OSM-tagg ──────────────────────────────────────────────────
# En ny bransch är en rad. Taggarna är OSM:s egna; att hitta på en egen
# taxonomi ovanpå hade betytt att en okänd bransch tyst räknat fel saker.
OSM_TAGS: dict[str, tuple[tuple[str, str], ...]] = {
    "frisor": (("shop", "hairdresser"),),
    "gym": (("leisure", "fitness_centre"),),
    "cafe": (("amenity", "cafe"),),
    "restaurang": (("amenity", "restaurant"),),
    "bageri": (("shop", "bakery"),),
    "apotek": (("amenity", "pharmacy"),),
    "tandlakare": (("amenity", "dentist"),),
    "veterinar": (("amenity", "veterinary"),),
    "optiker": (("shop", "optician"),),
    "bilverkstad": (("shop", "car_repair"),),
    "forskola": (("amenity", "kindergarten"),),
    "stadfirma": (("shop", "laundry"), ("shop", "dry_cleaning")),
    "lager": (("building", "warehouse"), ("landuse", "industrial")),
    "elektriker": (("craft", "electrician"),),
    "vvs": (("craft", "plumber"),),
    "malare": (("craft", "painter"),),
    "bygg": (("craft", "builder"), ("craft", "carpenter")),
    "taklaggare": (("craft", "roofer"),),
    "fysioterapi": (("healthcare", "physiotherapist"),),
    "aldreomsorg": (("amenity", "social_facility"),),
}


def _overpass_query(lat: float, lon: float, verticals: list[str],
                    radius_m: int) -> str:
    """ETT anrop som räknar alla branscher, inte ett per bransch.

    Overpass sänder ut en `count`-post per `out count`-sats, i samma
    ordning som satserna står. Ordningen är alltså kontraktet — den
    läses tillbaka på index i `_parse_overpass`.
    """
    delar = ["[out:json][timeout:120];"]
    for vid in verticals:
        block = []
        for nyckel, varde in OSM_TAGS[vid]:
            for typ in ("node", "way"):
                block.append(f'{typ}["{nyckel}"="{varde}"]'
                             f'(around:{radius_m},{lat},{lon});')
        delar.append("(" + "".join(block) + ");out count;")
    return "".join(delar)


def _parse_overpass(raw: bytes, verticals: list[str]) -> dict[str, int]:
    data = json.loads(raw.decode("utf-8"))
    poster = [e for e in (data.get("elements") or [])
              if (e or {}).get("type") == "count"]
    if len(poster) != len(verticals):
        # Antalet svar måste stämma med antalet frågor, annars vet vi
        # inte vilken bransch ett tal gäller — och ett tal på fel bransch
        # är värre än inget tal.
        raise ValueError(f"Overpass answered with {len(poster)} counts for "
                         f"{len(verticals)} queries; refusing to guess "
                         f"which is which")
    ut = {}
    for vid, post in zip(verticals, poster, strict=True):
        ut[vid] = int((post.get("tags") or {}).get("total", 0))
    return ut


def _harvest_news(region: tuple, source: dict, transport) -> list[dict]:
    """Nyhetsposter är INTE en signal med ett värde.

    Skörden går därför inte via `store_rows` utan via
    `engine/news.store_items` och tabellen `news_items`. Att trycka in en
    rubrik i `harvested` hade krävt ett `signal_id` som inte är en
    signal — och skördelagrets åldersregel hade då gällt fel sak.

    Regionen skickas in men används inte som frågeparameter: ett RSS-flöde
    tar inga koordinater. Posterna knyts till region EFTER hämtningen,
    på namn, och den matchningen är grov med flit (news.region_of).
    """
    from engine import news as N
    from engine.markets import MARKETS

    marknad = source.get("market", "")
    regioner = [r for m in ([marknad] if marknad in MARKETS else MARKETS)
                for r in MARKETS[m].regions]
    poster, trasiga = [], []
    for feed in N.feeds_for(marknad):
        raw = transport(feed["url"])
        if raw is None:
            continue
        try:
            hamtat = N.parse_feed(raw, feed["outlet"])
        except OUR_BUGS:
            raise
        except Exception as e:                # noqa: BLE001, S112
            # Ett trasigt flöde stoppar inte de andra, men det får inte
            # heller försvinna tyst: sju flöden som svarar och ett som
            # inte gör det ska gå att skilja från åtta som svarar.
            trasiga.append({"outlet": feed["outlet"],
                            "why_en": f"{type(e).__name__}: {e}"})
            continue
        for post in hamtat:
            post["market"] = feed["market"] or marknad
            post["region_code"] = N.region_of(post, regioner)
            post["checksum"] = N.item_checksum(post)
            post["harvested_at"] = _time.time()
            poster.append(post)
    n = N.store_items(poster)
    # Trasiga flöden lagras som en not på skörden i stället för att
    # skrivas till stdout: motorn skriver inte till terminalen, och sju
    # flöden som svarar ska gå att skilja från åtta.
    N.set_last_harvest({"items": n, "feeds": len(N.feeds_for(marknad)),
                        "unparsed": trasiga})
    # Returnerar tom lista: raderna ligger redan i sin egen tabell, och
    # att också lägga dem i `harvested` vore två sanningar om samma sak.
    return []


# ── US Census CBP: den första riktiga amerikanska referensen ────────────
# Metroregion → delstatskod. CBP svarar per DELSTAT, inte per metro: en
# metrosiffra vore mer exakt och kräver en annan tabell. Att använda
# delstatens tal och SÄGA att det är delstatens är bättre än att låtsas
# att det är stadens.
_CENSUS_STATE: dict[str, str] = {
    "us-newyork": "36", "us-losangeles": "06", "us-chicago": "17",
    "us-houston": "48", "us-phoenix": "04", "us-philadelphia": "42",
    "us-sanantonio": "48", "us-sandiego": "06", "us-dallas": "48",
    "us-austin": "48", "us-jacksonville": "12", "us-columbus": "39",
    "us-charlotte": "37", "us-indianapolis": "18", "us-seattle": "53",
    "us-denver": "08", "us-boston": "25", "us-nashville": "47",
    "us-detroit": "26", "us-portland": "41", "us-lasvegas": "32",
    "us-memphis": "47", "us-louisville": "21", "us-milwaukee": "55",
    "us-baltimore": "24", "us-atlanta": "13", "us-miami": "12",
    "us-minneapolis": "27", "us-tampa": "12", "us-stlouis": "29",
    "us-sanfrancisco": "06", "us-sanjose": "06", "us-sacramento": "06",
    "us-orlando": "12", "us-cleveland": "39", "us-pittsburgh": "42",
    "us-cincinnati": "39", "us-kansascity": "29", "us-neworleans": "22",
    "us-saltlakecity": "49", "us-raleigh": "37", "us-richmond": "51",
    "us-buffalo": "36", "us-hartford": "09", "us-providence": "44",
    "us-tulsa": "40", "us-oklahomacity": "40", "us-omaha": "31",
    "us-desmoines": "19", "us-boise": "16", "us-spokane": "53",
    "us-albuquerque": "35", "us-elpaso": "48", "us-tucson": "04",
    "us-fresno": "06", "us-virginiabeach": "51", "us-grandrapids": "26",
    "us-birmingham": "01", "us-jackson": "28", "us-littlerock": "05",
    "us-charleston": "45", "us-charlestonwv": "54", "us-wilmington": "10",
    "us-newark": "34", "us-manchester": "33", "us-burlington": "50",
    "us-portlandme": "23", "us-fargo": "38", "us-siouxfalls": "46",
    "us-billings": "30", "us-cheyenne": "56", "us-anchorage": "02",
    "us-honolulu": "15", "us-wichita": "20", "us-washington": "11",
}


def _harvest_census(region: tuple, source: dict, transport) -> list[dict]:
    """Arbetsställen per delstat. Nyckellöst vid låg volym.

    Det här är källan som lyfter USA över MRAI:s täckningsgrind. I dag är
    varenda signal där mock, och ett index på det underlaget hade mätt vår
    egen blindhet och lästs som ett omdöme om landets press.

    Svarsform (dokumenterad): [["ESTAB","NAME","state"],
                               ["123456","Texas","48"]]
    """
    kod = region[0]
    stat = _CENSUS_STATE.get(kod)
    if not stat:
        return []          # ingen delstatskod → inget påhittat svar
    url = (f"{source['url']}/data/2021/cbp?"
           + urllib.parse.urlencode({"get": "ESTAB,NAME",
                                     "for": f"state:{stat}"}))
    raw = transport(url)
    if raw is None:
        return []
    rader = json.loads(raw.decode("utf-8"))
    if not isinstance(rader, list) or len(rader) < 2:
        return []
    rubrik = [str(x).upper() for x in rader[0]]
    if "ESTAB" not in rubrik:
        return []
    varde = float(rader[1][rubrik.index("ESTAB")])
    return [{"source": "census_cbp", "region_code": kod,
             "signal_id": "business_density", "value": varde,
             "unit": "units", "lat": region[2], "lon": region[3],
             "observed_scope": f"state:{stat}"}]


# ── Kolada: den anmälda halvan av uppmärksamhetsindexet ─────────────────
_KOLADA_KPI = "N07403"     # anmälda våldsbrott PER 100 000 INVÅNARE


def _harvest_kolada(region: tuple, source: dict, transport) -> list[dict]:
    """Svenska kommuners nyckeltal. Nyckellöst.

    N07403 är en KVOT per 100 000, inte ett antal. Att blanda den med ett
    rått artikelantal hade gjort uppmärksamhetsindexet till en
    befolkningsmätare — därför normaliserar news.attention_index båda
    sidor och vägrar när befolkningen saknas.

    Svarsform: {"values": [{"kpi": .., "municipality": "0180",
    "period": 2024, "values": [{"value": 1234.5, "gender": "T"}]}]}
    """
    kod = region[0]
    if not (kod.isdigit() and len(kod) == 4):
        return []          # Kolada är svenska kommunkoder, inget annat
    raw = transport(f"{source['url']}/v2/data/kpi/{_KOLADA_KPI}"
                    f"/municipality/{kod}")
    if raw is None:
        return []
    poster = (json.loads(raw.decode("utf-8")) or {}).get("values") or []
    senaste = None
    for p in poster:
        for v in p.get("values") or []:
            if v.get("gender") in ("T", None) and \
                    isinstance(v.get("value"), (int, float)):
                if senaste is None or p.get("period", 0) >= senaste[0]:
                    senaste = (p.get("period", 0), float(v["value"]))
    if senaste is None:
        return []
    return [{"source": "kolada_crime", "region_code": kod,
             "signal_id": "crime_index", "value": senaste[1],
             "unit": "per 100k", "lat": region[2], "lon": region[3],
             "period": senaste[0]}]


def _harvest_osm(region: tuple, source: dict, transport) -> list[dict]:
    kod, _namn, lat, lon = region[0], region[1], region[2], region[3]
    verticals = sorted(OSM_TAGS)
    fraga = _overpass_query(lat, lon, verticals, DEFAULT_RADIUS_M)
    # Breaker.fetch lägger själv på sin timeout sist. Att skicka en till
    # här gav transporten fyra argument, TypeError, och en skörd som
    # tyst lagrade noll rader i produktion — fångat av testet, inte av en
    # användare.
    raw = transport(source["url"],
                    urllib.parse.urlencode({"data": fraga}).encode("utf-8"))
    if raw is None:
        return []
    antal = _parse_overpass(raw, verticals)
    rader = []
    for vid, n in antal.items():
        rader.append({
            "source": "osm", "region_code": kod,
            # Signalen är per BRANSCH. Nyckeln bär den, annars hade
            # frisörernas antal svarat för bilverkstäderna.
            "signal_id": f"competition_pressure:{vid}",
            # Samma skala som places.py redan använder: min(10, n). Att
            # införa en andra skala för samma signal hade betytt att två
            # källor svarat i olika enheter.
            "value": float(min(10, n)),
            "unit": "0–10", "observed_count": n,
            "lat": lat, "lon": lon,
        })
    return rader


def _harvest_open_meteo(region: tuple, source: dict, transport) -> list[dict]:
    kod, lat, lon = region[0], region[2], region[3]
    url = (f"{source['url']}/v1/forecast?"
           + urllib.parse.urlencode({
               "latitude": lat, "longitude": lon,
               "current": "temperature_2m,precipitation",
               "timezone": "UTC"}))
    raw = transport(url)
    if raw is None:
        return []
    nu = (json.loads(raw.decode("utf-8")) or {}).get("current") or {}
    rader = []
    for falt, sid, enhet in (("temperature_2m", "air_temperature_c", "°C"),
                             ("precipitation", "precipitation_mm", "mm")):
        v = nu.get(falt)
        if isinstance(v, (int, float)):
            rader.append({"source": "open_meteo", "region_code": kod,
                          "signal_id": sid, "value": float(v),
                          "unit": enhet, "lat": lat, "lon": lon})
    return rader


# ── Källorna ────────────────────────────────────────────────────────────
SOURCES: dict[str, dict] = {
    "osm": {
        "label_en": "OpenStreetMap (Overpass)",
        "fills_en": "Observed competing supply per industry",
        "signals": ("competition_pressure",),
        "env": "LANDVEX_OSM_URL",
        "default_url": "https://overpass-api.de/api/interpreter",
        "keyless": True,
        "markets": (),              # ingen geografisk gräns
        "max_age_days": 30,         # OSM ändras långsamt
        "quality": 0.5,
        "post": True,
        "harvest": _harvest_osm,
        "cannot_en": (
            "Crowd-mapped. An unmapped hairdresser still exists, and "
            "coverage differs between a mapped city centre and a rural "
            "municipality — absence here is not absence on the ground. "
            "It is observed supply, never a count of registered "
            "businesses: /v1/saturation still refuses where no business "
            "register is connected."),
    },
    "news": {
        "label_en": "News feeds (RSS/Atom)",
        "fills_en": "Corroborated reporting — never a signal value",
        "signals": (),
        "env": "LANDVEX_NEWS_ON",
        # Nyheter har ingen ENDA adress — de har åtta, och de står som
        # data i engine/news.FEEDS. Sentinelvärdet gör källan påslagbar
        # av LANDVEX_OPEN_DATA utan att låtsas att det finns en URL.
        "default_url": "feeds://engine.news.FEEDS",
        "keyless": True,
        "markets": (),
        "max_age_days": 7,
        "quality": 0.4,
        "post": False,
        "harvest": _harvest_news,
        "cannot_en": (
            "News never becomes a signal value. A corroborated item can "
            "raise a RISK BAND and name the outlets behind it; a headline "
            "that could set a number would make this a rumour amplifier "
            "with an API. Items are attached to a region by NAME, which "
            "is a mention and not a subject."),
    },
    "census_cbp": {
        "label_en": "US Census County Business Patterns",
        "fills_en": "Establishment counts — the first real US reference",
        "signals": ("business_density",),
        "env": "LANDVEX_CENSUS_BASE",
        "default_url": "https://api.census.gov",
        "keyless": True,
        "markets": ("us",),
        "max_age_days": 365,
        "quality": 0.5,
        "post": False,
        "harvest": _harvest_census,
        "cannot_en": (
            "CBP answers per STATE, not per metro region: the number is "
            "the state's and is attached to the metro inside it. A metro "
            "figure would be more precise and needs a different table — "
            "saying which is which is better than pretending. It is also "
            "a year or more old by publication, which is right for "
            "structure and wrong for change."),
    },
    "kolada_crime": {
        "label_en": "Kolada — reported violent crime per 100k",
        "fills_en": "The REPORTED half of the attention index",
        "signals": ("crime_index",),
        "env": "LANDVEX_KOLADA_URL",
        "default_url": "https://api.kolada.se",
        "keyless": True,
        "markets": ("se",),
        "max_age_days": 365,
        "quality": 0.8,
        "post": False,
        "harvest": _harvest_kolada,
        "cannot_en": (
            "Reported is not occurred. Propensity to report varies "
            "sharply between offence types and between groups, and the "
            "dark figure is a different size in every municipality — this "
            "is the register's number, not the street's."),
    },
    "open_meteo": {
        "label_en": "Open-Meteo",
        "fills_en": "Weather — the only network with global reach",
        "signals": ("air_temperature_c", "precipitation_mm"),
        "env": "LANDVEX_METEO_URL",
        "default_url": "https://api.open-meteo.com",
        "keyless": True,
        "markets": (),
        "max_age_days": 1,          # väder åldras på timmar
        "quality": 0.7,
        "post": False,
        "harvest": _harvest_open_meteo,
        "cannot_en": (
            "A model reanalysis at a grid point, not a station reading. "
            "It is the right thing for ruling weather OUT as an "
            "explanation, and the wrong thing to quote as an "
            "observation."),
    },
}


def url_for(source_id: str) -> str:
    """Bas-URL för en källa. LANDVEX_OPEN_DATA=on fyller i den
    dokumenterade default-adressen för NYCKELLÖSA källor — och bara för
    dem. En källa som kräver nyckel slås aldrig på av en omställare."""
    s = SOURCES[source_id]
    egen = os.environ.get(s["env"], "")
    if egen:
        return egen.rstrip("/")
    if open_data_on() and s["keyless"]:
        return s["default_url"].rstrip("/")
    return ""


def open_data_on() -> bool:
    return os.environ.get("LANDVEX_OPEN_DATA", "off").lower() in (
        "on", "1", "true", "yes")


def switchable_today() -> list[dict]:
    """Vad som går att slå på NU, utan att ansöka om någonting."""
    return [{"source": sid, "label_en": s["label_en"],
             "fills_en": s["fills_en"], "env": s["env"],
             "default_url": s["default_url"],
             "active": bool(url_for(sid)),
             "markets": list(s["markets"]) or ["any"]}
            for sid, s in SOURCES.items() if s["keyless"]]


# ── Skörden ─────────────────────────────────────────────────────────────
def harvest_region(source_id: str, region: tuple, market: str, *,
                   transport=None, timeout: float = 90.0) -> list[dict]:
    """Hämta EN region från EN källa. Tom lista när källan inte är på."""
    s = SOURCES[source_id]
    url = url_for(source_id)
    if not url:
        return []
    if s["markets"] and market not in s["markets"]:
        return []
    breaker = Breaker(transport or (_http_post if s["post"] else _http_get),
                      timeout=timeout)
    try:
        rader = s["harvest"](region, {**s, "url": url, "timeout": timeout},
                             breaker.fetch)
    except OUR_BUGS:
        raise
    except Exception:                                   # noqa: BLE001
        return []
    nu = time.time()
    for r in rader:
        r["market"] = market
        r["observed_at"] = nu
    return rader


# ── Lagret ──────────────────────────────────────────────────────────────
_STORE = None
_MINNE: dict[tuple, dict] = {}       # fallback utan lager, per process


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def store_rows(rader: list[dict]) -> int:
    if not rader:
        return 0
    if _STORE is not None and getattr(_STORE, "save_harvested", None):
        return _STORE.save_harvested(rader)
    for r in rader:
        _MINNE[(r["source"], r["region_code"], r["signal_id"])] = dict(r)
    return len(rader)


def all_rows(source_id: str = "") -> list[dict]:
    rader = (_STORE.all_harvested() if _STORE is not None
             and getattr(_STORE, "all_harvested", None)
             else list(_MINNE.values()))
    return [r for r in rader if not source_id or r["source"] == source_id]


def reset() -> None:
    """Endast för tester."""
    _MINNE.clear()


def read(source_id: str, lat: float, lon: float, signal_ids: list[str], *,
         now: float = 0.0) -> dict[str, dict]:
    """Skördade värden för en punkt. Tomt när inget är färskt och nära.

    Två skäl att INTE svara, och de är olika: raden finns men är för
    gammal, eller den närmaste raden ligger för långt bort. Båda ger
    tomt — motorn faller till mock, och `data_coverage` sjunker som den
    ska.
    """
    s = SOURCES.get(source_id)
    if s is None:
        return {}
    nu = now or time.time()
    tak = s["max_age_days"] * 86400
    onskade = set(signal_ids)
    basta: dict[str, tuple[float, dict]] = {}
    for r in all_rows(source_id):
        sid = r["signal_id"]
        if sid not in onskade:
            continue
        if (nu - float(r.get("observed_at") or 0)) > tak:
            continue                     # för gammal = frånvarande
        d = _km(lat, lon, float(r["lat"]), float(r["lon"]))
        if d > MATCH_RADIUS_KM:
            continue
        if sid not in basta or d < basta[sid][0]:
            basta[sid] = (d, r)
    return {sid: {**r, "distance_km": round(d, 1),
                  "age_days": round((nu - float(r["observed_at"])) / 86400, 2),
                  "quality": s["quality"]}
            for sid, (d, r) in basta.items()}


def catalog() -> dict:
    return {
        "sources": [{k: v for k, v in s.items()
                     if k not in ("harvest",)} | {"id": sid,
                                                  "active": bool(url_for(sid))}
                    for sid, s in SOURCES.items()],
        "industries_mapped": len(OSM_TAGS),
        "match_radius_km": MATCH_RADIUS_KM,
        "open_data_on": open_data_on(),
        "principle_en": (
            "Open sources are read once a day and stored. The request "
            "path never calls a third party: a 700 ms answer budget "
            "cannot contain a multi-second Overpass query, a public "
            "service should not be asked the same question by every "
            "visitor, and the same question twice must return the same "
            "answer."),
        "cannot_en": (
            "Harvested data is as old as its last harvest. A row past "
            "its source's max_age_days is treated as ABSENT rather than "
            "served quietly, so a stale number can never masquerade as a "
            "fresh one — the answer falls back to the labelled mock and "
            "data_coverage drops accordingly."),
    }
