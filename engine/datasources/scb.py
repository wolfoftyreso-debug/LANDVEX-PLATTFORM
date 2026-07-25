"""SCB-klient (PxWeb) + signalberäkningar för ScbSource.

Endast stdlib (urllib) – adaptern hör till engine/ och ska kunna köras
i Lambda utan installation. HTTP-transporten är injicerbar så att
tester körs helt utan nätverk (fixturer i tests/test_scb.py).

Datanivå i denna version: KOMMUN. Det är en medveten första nivå –
kommunstatistik appliceras på platsens upptagningsområde och märks med
lägre quality än framtida DeSO/rutnätsdata. Byts mot DeSO när
persistens + geodata (PostGIS) finns (backlog #2–3).

Tabellsökvägar nedan är satta enligt SCB:s statistikdatabas men ska
live-verifieras med proben innan produktionssättning (nätverket i
utvecklingsmiljön tillät inte api.scb.se vid implementationstillfället):

    python3 -m engine.datasources.scb 59.3145 18.0705

Frågebyggnaden är metadatadriven (build_query läser tabellens
variabler) just för att tåla mindre skillnader i dimensioner och
innehållskoder mellan tabellversioner.
"""
from __future__ import annotations

import itertools
import json
import math
import time
import os
import urllib.request
from typing import Any, Callable

# Base + table paths are env-overridable so they can be corrected against
# the live SCB API WITHOUT a code change (paths must be live-verified — SCB
# has migrated its PxWeb structure; use scripts/scb_probe.py --discover to
# navigate the current tree, then set these).
PXWEB_BASE = os.environ.get(
    "LANDVEX_SCB_BASE", "https://api.scb.se/OV0104/v1/doris/sv/ssd")

# Tabeller (relativt PXWEB_BASE). Verifieras med proben – se moduldoc.
POP_TABLE = os.environ.get(
    "LANDVEX_SCB_POP_TABLE", "BE/BE0101/BE0101A/BefolkningNy")     # folkmängd
DENSITY_TABLE = os.environ.get(
    "LANDVEX_SCB_DENSITY_TABLE", "BE/BE0101/BE0101C/BefArealTathetKon")
INCOME_TABLE = os.environ.get(
    "LANDVEX_SCB_INCOME_TABLE", "HE/HE0110/HE0110A/SamForvInk2")   # förvärvsink.

RIKET = "00"
PERSONS_PER_HOUSEHOLD = 2.2   # SCB-rikssnitt ~2,2 pers/hushåll (för hh/km²)


class ScbError(Exception):
    pass


def _http_transport(url: str, payload: bytes | None, timeout: float) -> bytes:
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json",
                 "User-Agent": "landvex-opportunity-engine/0.2"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


class ScbClient:
    """Tunn PxWeb-klient med in-memory-cache per (tabell, fråga)."""

    def __init__(self, base: str = PXWEB_BASE,
                 transport: Callable[[str, bytes | None, float], bytes] | None = None,
                 timeout: float = 6.0, ttl_s: float = 24 * 3600.0,
                 clock: Callable[[], float] = time.monotonic):
        self.base = base.rstrip("/")
        self._transport = transport or _http_transport
        self.timeout = timeout
        self.ttl_s = ttl_s
        self._clock = clock
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cached(self, key: str, load: Callable[[], Any]) -> Any:
        hit = self._cache.get(key)
        now = self._clock()
        if hit and now - hit[0] < self.ttl_s:
            return hit[1]
        doc = load()
        self._cache[key] = (now, doc)
        return doc

    def meta(self, table: str) -> dict:
        url = f"{self.base}/{table}"
        return self._cached(f"meta:{table}", lambda: json.loads(
            self._transport(url, None, self.timeout).decode("utf-8")))

    def data(self, table: str, query: list[dict]) -> dict:
        url = f"{self.base}/{table}"
        body = json.dumps({"query": query,
                           "response": {"format": "json-stat2"}}).encode("utf-8")
        key = f"data:{table}:{json.dumps(query, sort_keys=True)}"
        return self._cached(key, lambda: json.loads(
            self._transport(url, body, self.timeout).decode("utf-8")))


# ── Frågebyggnad ─────────────────────────────────────────────────────

_TOTAL_WORDS = ("totalt", "samtliga", "tot")


def build_query(meta: dict, region: list[str], time_top: int,
                contents_like: tuple[str, ...],
                take_all: tuple[str, ...] = ()) -> list[dict]:
    """Bygger PxWeb-fråga från tabellens metadata.

    Region väljs explicit, Tid som senaste `time_top`, innehållsserie
    via etikettmatchning (första träff). Övriga dimensioner elimineras
    om möjligt, annars väljs "totalt"-kategorin, annars alla värden.
    """
    query: list[dict] = []
    for var in meta.get("variables", []):
        code, texts, values = var["code"], var.get("valueTexts", []), var.get("values", [])
        if code == "Region":
            query.append({"code": code, "selection": {"filter": "item", "values": region}})
        elif var.get("time") or code == "Tid":
            query.append({"code": code, "selection": {"filter": "top", "values": [str(time_top)]}})
        elif code == "ContentsCode":
            picked = [v for v, t in zip(values, texts)
                      if any(w in t.lower() for w in contents_like)]
            if not picked:
                raise ScbError(f"No contents series matches {contents_like} "
                               f"in the table.")
            query.append({"code": code, "selection": {"filter": "item", "values": picked[:1]}})
        elif code in take_all:
            query.append({"code": code, "selection": {"filter": "item", "values": list(values)}})
        elif var.get("elimination"):
            continue
        else:
            total = [v for v, t in zip(values, texts)
                     if t.lower().strip() in _TOTAL_WORDS or
                     any(t.lower().startswith(w) for w in _TOTAL_WORDS)]
            query.append({"code": code, "selection": {
                "filter": "item", "values": total[:1] or list(values)}})
    return query


# ── JSON-stat2 ───────────────────────────────────────────────────────

class JsonStat:
    """Minimal läsare för JSON-stat2 (radmajor ordning enligt id/size)."""

    def __init__(self, doc: dict):
        self.doc = doc
        self.dims: list[str] = doc["id"]
        self.size: list[int] = doc["size"]
        self.values: list = doc["value"]

    def _index(self, dim: str) -> dict[str, int]:
        idx = self.doc["dimension"][dim]["category"]["index"]
        if isinstance(idx, list):
            return {c: i for i, c in enumerate(idx)}
        return idx

    def codes(self, dim: str) -> list[str]:
        idx = self._index(dim)
        return [c for c, _ in sorted(idx.items(), key=lambda kv: kv[1])]

    def cells(self, fixed: dict[str, str]):
        """Genererar (koordinater, värde) för alla celler som matchar fixed."""
        free = [d for d in self.dims if d not in fixed]
        for combo in itertools.product(*(self.codes(d) for d in free)):
            coords = dict(fixed, **dict(zip(free, combo)))
            lin = 0
            for d, n in zip(self.dims, self.size):
                lin = lin * n + self._index(d)[coords[d]]
            v = self.values[lin]
            if v is not None:
                yield coords, float(v)

    def total(self, fixed: dict[str, str]) -> float:
        return sum(v for _, v in self.cells(fixed))

    def mean(self, fixed: dict[str, str]) -> float:
        vals = [v for _, v in self.cells(fixed)]
        if not vals:
            raise ScbError(f"No cells for {fixed}.")
        return sum(vals) / len(vals)


def _parse_age(code: str) -> int | None:
    c = code.strip().rstrip("+")
    return int(c) if c.isdigit() else None


# ── Signalberäkningar (kommunnivå) ───────────────────────────────────

def population_signals(client: ScbClient, kommun: str) -> tuple[dict[str, float], dict]:
    """pop_growth_pct, age_20_45_share, share_65plus + extras."""
    meta = client.meta(POP_TABLE)
    query = build_query(meta, region=[kommun], time_top=2,
                        contents_like=("folkmängd",), take_all=("Alder",))
    stat = JsonStat(client.data(POP_TABLE, query))
    years = sorted(stat.codes("Tid"))
    if not years:
        raise ScbError("No years in the population response.")
    latest = years[-1]

    def ages_for(year: str) -> dict[int, float]:
        out: dict[int, float] = {}
        for code in stat.codes("Alder"):
            age = _parse_age(code)
            if age is None:            # hoppa "totalt"/"uppgift saknas"
                continue
            out[age] = out.get(age, 0.0) + stat.total(
                {"Region": kommun, "Tid": year, "Alder": code})
        return out

    ages = ages_for(latest)
    total = sum(ages.values())
    if total <= 0:
        raise ScbError("Empty population in the response.")

    signals: dict[str, float] = {
        "age_20_45_share": round(
            sum(v for a, v in ages.items() if 20 <= a <= 45) / total * 100, 1),
        "share_65plus": round(
            sum(v for a, v in ages.items() if a >= 65) / total * 100, 1),
    }
    if len(years) >= 2:
        prev_total = sum(ages_for(years[-2]).values())
        if prev_total > 0:
            signals["pop_growth_pct"] = round(
                (total - prev_total) / prev_total * 100, 1)
    return signals, {"ar": latest, "folkmangd_kommun": int(total)}


def income_index_signal(client: ScbClient, kommun: str) -> float:
    """Medelinkomst kommun / riket * 100."""
    meta = client.meta(INCOME_TABLE)
    query = build_query(meta, region=[kommun, RIKET], time_top=1,
                        contents_like=("medelinkomst",))
    stat = JsonStat(client.data(INCOME_TABLE, query))
    latest = sorted(stat.codes("Tid"))[-1]
    kommun_mean = stat.mean({"Region": kommun, "Tid": latest})
    riket_mean = stat.mean({"Region": RIKET, "Tid": latest})
    if riket_mean <= 0:
        raise ScbError("National mean income missing.")
    return round(kommun_mean / riket_mean * 100, 1)


def density_signal(client: ScbClient, kommun: str) -> float:
    """Befolkningstäthet (inv/km²) → hushåll/km² via rikssnitt."""
    meta = client.meta(DENSITY_TABLE)
    query = build_query(meta, region=[kommun], time_top=1,
                        contents_like=("täthet", "per kvadratkilometer"))
    stat = JsonStat(client.data(DENSITY_TABLE, query))
    latest = sorted(stat.codes("Tid"))[-1]
    density = stat.total({"Region": kommun, "Tid": latest})
    if density <= 0:
        raise ScbError("Density missing in the response.")
    return round(density / PERSONS_PER_HOUSEHOLD, 0)


# ── Kommunlokalisering ───────────────────────────────────────────────
# Närmaste-centroid över ett urval kommuner. Medveten v0.2-förenkling:
# täcker de större kommunerna; utanför tröskeln → None → mock-fallback
# (ärlig datatäckning). Ersätts av DeSO-polygoner i PostGIS-fasen.

KOMMUNER: list[tuple[str, str, float, float]] = [
    ("0180", "Stockholm", 59.33, 18.06),
    ("0181", "Södertälje", 59.20, 17.63),
    ("0182", "Nacka", 59.31, 18.16),
    ("0184", "Solna", 59.36, 18.00),
    ("0160", "Täby", 59.44, 18.07),
    ("0191", "Sigtuna", 59.62, 17.72),
    # Stockholms län fullt ut – gör grannkommuner till en verklig
    # jämförelsegrupp (mättnad mäts mot jämförbara platser, inte mot riket).
    ("0114", "Upplands Väsby", 59.52, 17.91),
    ("0115", "Vallentuna", 59.53, 18.08),
    ("0117", "Österåker", 59.48, 18.30),
    ("0120", "Värmdö", 59.32, 18.44),
    ("0123", "Järfälla", 59.42, 17.83),
    ("0125", "Ekerö", 59.29, 17.80),
    ("0126", "Huddinge", 59.24, 17.98),
    ("0127", "Botkyrka", 59.20, 17.83),
    ("0128", "Salem", 59.20, 17.77),
    ("0136", "Haninge", 59.17, 18.14),
    ("0138", "Tyresö", 59.24, 18.23),
    ("0139", "Upplands-Bro", 59.52, 17.63),
    ("0140", "Nykvarn", 59.18, 17.43),
    ("0162", "Danderyd", 59.40, 18.03),
    ("0163", "Sollentuna", 59.43, 17.95),
    ("0183", "Sundbyberg", 59.36, 17.97),
    ("0186", "Lidingö", 59.37, 18.14),
    ("0187", "Vaxholm", 59.40, 18.35),
    ("0188", "Norrtälje", 59.76, 18.70),
    ("0192", "Nynäshamn", 58.90, 17.95),
    ("0380", "Uppsala", 59.86, 17.64),
    ("0480", "Nyköping", 58.75, 17.01),
    ("0484", "Eskilstuna", 59.37, 16.51),
    ("0580", "Linköping", 58.41, 15.62),
    ("0581", "Norrköping", 58.59, 16.19),
    ("0680", "Jönköping", 57.78, 14.16),
    ("0780", "Växjö", 56.88, 14.81),
    ("0880", "Kalmar", 56.66, 16.36),
    ("0980", "Gotland", 57.64, 18.30),
    ("1080", "Karlskrona", 56.16, 15.59),
    ("1280", "Malmö", 55.60, 13.00),
    ("1281", "Lund", 55.70, 13.19),
    ("1283", "Helsingborg", 56.05, 12.69),
    ("1290", "Kristianstad", 56.03, 14.16),
    ("1380", "Halmstad", 56.67, 12.86),
    ("1383", "Varberg", 57.11, 12.25),
    ("1480", "Göteborg", 57.71, 11.97),
    ("1485", "Uddevalla", 58.35, 11.94),
    ("1488", "Trollhättan", 58.28, 12.29),
    ("1490", "Borås", 57.72, 12.94),
    ("1496", "Skövde", 58.39, 13.85),
    ("1780", "Karlstad", 59.38, 13.50),
    ("1880", "Örebro", 59.27, 15.21),
    ("1980", "Västerås", 59.61, 16.55),
    ("2080", "Falun", 60.61, 15.63),
    ("2081", "Borlänge", 60.48, 15.42),
    ("2180", "Gävle", 60.67, 17.14),
    ("2281", "Sundsvall", 62.39, 17.31),
    ("2284", "Örnsköldsvik", 63.29, 18.72),
    ("2380", "Östersund", 63.18, 14.64),
    ("2480", "Umeå", 63.83, 20.26),
    ("2482", "Skellefteå", 64.75, 20.95),
    ("2580", "Luleå", 65.58, 22.15),
    ("2584", "Kiruna", 67.86, 20.23),
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class KommunLocator:
    def __init__(self, max_km: float = 30.0,
                 kommuner: list[tuple[str, str, float, float]] | None = None):
        self.max_km = max_km
        self.kommuner = kommuner or KOMMUNER

    def locate(self, lat: float, lon: float) -> tuple[str, str] | None:
        best, best_km = None, float("inf")
        for code, name, klat, klon in self.kommuner:
            d = _haversine_km(lat, lon, klat, klon)
            if d < best_km:
                best, best_km = (code, name), d
        return best if best is not None and best_km <= self.max_km else None


# ── Live-prob (kräver nätverk mot api.scb.se) ────────────────────────

if __name__ == "__main__":
    import sys

    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 59.3145
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 18.0705
    hit = KommunLocator().locate(lat, lon)
    if not hit:
        sys.exit("No municipality within the threshold – extend KOMMUNER "
                 "or provide another point.")
    code, name = hit
    print(f"Municipality: {name} ({code})")
    client = ScbClient()
    sig, extra = population_signals(client, code)
    print(f"Population: {extra}  →  {sig}")
    print(f"income_index: {income_index_signal(client, code)}")
    print(f"residential_density (hh/km²): {density_signal(client, code)}")
