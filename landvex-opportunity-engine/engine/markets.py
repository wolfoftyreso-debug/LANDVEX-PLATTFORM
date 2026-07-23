"""Marknadsmodellen – fullt utbyggd för USA och Europa.

Varje marknad (land) definieras som data: regioner med koordinater,
kartprojektion (bbox), regionbenämning och valuta. Motorerna är
platsagnostiska – samma modell körs överallt; det som skiljer länder
åt är datakällorna i Resolver-kedjan (SCB för Sverige; Eurostat,
Destatis, INE, GUS, INSEE, Census/BLS m.fl. i produktionsfasen) och
regionlistan här.

Regionlistorna är centroidfrön för större städer/storstadsregioner.
All icke-svensk data är mockad tills lokala adaptrar kopplas –
data_coverage och konfidens redovisar det ärligt.

Gemensam Opportunity Score över länder förutsätter samma normalise-
ring överallt – därför äger signalkatalogen skalorna, inte länderna.
"""
from __future__ import annotations

from dataclasses import dataclass

from .datasources.scb import KOMMUNER


@dataclass(frozen=True)
class Market:
    id: str
    label_en: str
    currency: str
    region_label_en: str
    bbox: tuple            # (lat_min, lat_max, lon_min, lon_max)
    regions: tuple         # ((kod, namn, lat, lon), ...)
    calibrated: bool = False   # ekonomischabloner kalibrerade för marknaden?


def _r(*rows):
    return tuple(rows)


MARKETS: dict[str, Market] = {m.id: m for m in [
    Market("se", "Sweden", "SEK", "municipality",
           (55.0, 69.5, 10.5, 24.5), tuple(KOMMUNER), calibrated=True),

    Market("us", "USA", "USD", "metro region",
           (24.0, 50.0, -125.0, -66.0), _r(
        ("us-newyork", "New York", 40.71, -74.01),
        ("us-losangeles", "Los Angeles", 34.05, -118.24),
        ("us-chicago", "Chicago", 41.88, -87.63),
        ("us-houston", "Houston", 29.76, -95.37),
        ("us-phoenix", "Phoenix", 33.45, -112.07),
        ("us-dallas", "Dallas", 32.78, -96.80),
        ("us-miami", "Miami", 25.76, -80.19),
        ("us-atlanta", "Atlanta", 33.75, -84.39),
        ("us-denver", "Denver", 39.74, -104.99),
        ("us-seattle", "Seattle", 47.61, -122.33),
        ("us-boston", "Boston", 42.36, -71.06),
        ("us-austin", "Austin", 30.27, -97.74),
        ("us-nashville", "Nashville", 36.16, -86.78),
        ("us-minneapolis", "Minneapolis", 44.98, -93.27),
        ("us-charlotte", "Charlotte", 35.23, -80.84),
        ("us-sanfrancisco", "San Francisco", 37.77, -122.42),
        ("us-sandiego", "San Diego", 32.72, -117.16),
        ("us-sanjose", "San Jose", 37.34, -121.89),
        ("us-philadelphia", "Philadelphia", 39.95, -75.17),
        ("us-washington", "Washington DC", 38.91, -77.04),
        ("us-detroit", "Detroit", 42.33, -83.05),
        ("us-tampa", "Tampa", 27.95, -82.46),
        ("us-orlando", "Orlando", 28.54, -81.38),
        ("us-stlouis", "St. Louis", 38.63, -90.20),
        ("us-baltimore", "Baltimore", 39.29, -76.61),
        ("us-portland", "Portland", 45.52, -122.68),
        ("us-lasvegas", "Las Vegas", 36.17, -115.14),
        ("us-sanantonio", "San Antonio", 29.42, -98.49),
        ("us-sacramento", "Sacramento", 38.58, -121.49),
        ("us-kansascity", "Kansas City", 39.10, -94.58),
        ("us-columbus", "Columbus", 39.96, -83.00),
        ("us-indianapolis", "Indianapolis", 39.77, -86.16),
        ("us-cleveland", "Cleveland", 41.50, -81.69),
        ("us-cincinnati", "Cincinnati", 39.10, -84.51),
        ("us-pittsburgh", "Pittsburgh", 40.44, -79.99),
        ("us-saltlakecity", "Salt Lake City", 40.76, -111.89),
        ("us-raleigh", "Raleigh", 35.78, -78.64),
        ("us-milwaukee", "Milwaukee", 43.04, -87.91),
        ("us-oklahomacity", "Oklahoma City", 35.47, -97.52),
        ("us-neworleans", "New Orleans", 29.95, -90.07))),

    Market("de", "Germany", "EUR", "metro region",
           (47.0, 55.2, 5.5, 15.5), _r(
        ("de-berlin", "Berlin", 52.52, 13.40),
        ("de-hamburg", "Hamburg", 53.55, 10.00),
        ("de-munchen", "München", 48.14, 11.58),
        ("de-koln", "Köln", 50.94, 6.96),
        ("de-frankfurt", "Frankfurt", 50.11, 8.68),
        ("de-stuttgart", "Stuttgart", 48.78, 9.18),
        ("de-dusseldorf", "Düsseldorf", 51.23, 6.78),
        ("de-leipzig", "Leipzig", 51.34, 12.37),
        ("de-dortmund", "Dortmund", 51.51, 7.47),
        ("de-dresden", "Dresden", 51.05, 13.74),
        ("de-hannover", "Hannover", 52.37, 9.73),
        ("de-nurnberg", "Nürnberg", 49.45, 11.08),
        ("de-bremen", "Bremen", 53.08, 8.81),
        ("de-essen", "Essen", 51.46, 7.01),
        ("de-mannheim", "Mannheim", 49.49, 8.47),
        ("de-munster", "Münster", 51.96, 7.63),
        ("de-bonn", "Bonn", 50.73, 7.10),
        ("de-karlsruhe", "Karlsruhe", 49.01, 8.40),
        ("de-wiesbaden", "Wiesbaden", 50.08, 8.24),
        ("de-augsburg", "Augsburg", 48.37, 10.90),
        ("de-kiel", "Kiel", 54.32, 10.14),
        ("de-rostock", "Rostock", 54.09, 12.14),
        ("de-freiburg", "Freiburg", 47.99, 7.85),
        ("de-mainz", "Mainz", 50.00, 8.27))),

    Market("fr", "France", "EUR", "metro region",
           (41.0, 51.5, -5.5, 9.5), _r(
        ("fr-paris", "Paris", 48.86, 2.35),
        ("fr-marseille", "Marseille", 43.30, 5.37),
        ("fr-lyon", "Lyon", 45.76, 4.84),
        ("fr-toulouse", "Toulouse", 43.60, 1.44),
        ("fr-nice", "Nice", 43.70, 7.27),
        ("fr-nantes", "Nantes", 47.22, -1.55),
        ("fr-strasbourg", "Strasbourg", 48.57, 7.75),
        ("fr-montpellier", "Montpellier", 43.61, 3.88),
        ("fr-bordeaux", "Bordeaux", 44.84, -0.58),
        ("fr-lille", "Lille", 50.63, 3.06),
        ("fr-rennes", "Rennes", 48.11, -1.68),
        ("fr-grenoble", "Grenoble", 45.19, 5.72),
        ("fr-nancy", "Nancy", 48.69, 6.18),
        ("fr-rouen", "Rouen", 49.44, 1.10),
        ("fr-dijon", "Dijon", 47.32, 5.04))),

    Market("es", "Spain", "EUR", "region",
           (35.5, 44.0, -10.0, 4.5), _r(
        ("es-madrid", "Madrid", 40.42, -3.70),
        ("es-barcelona", "Barcelona", 41.39, 2.17),
        ("es-valencia", "Valencia", 39.47, -0.38),
        ("es-sevilla", "Sevilla", 37.39, -5.99),
        ("es-zaragoza", "Zaragoza", 41.65, -0.88),
        ("es-malaga", "Málaga", 36.72, -4.42),
        ("es-murcia", "Murcia", 37.99, -1.13),
        ("es-palma", "Palma", 39.57, 2.65),
        ("es-bilbao", "Bilbao", 43.26, -2.93),
        ("es-alicante", "Alicante", 38.35, -0.48),
        ("es-valladolid", "Valladolid", 41.65, -4.72),
        ("es-vigo", "Vigo", 42.24, -8.72),
        ("es-granada", "Granada", 37.18, -3.60),
        ("es-coruna", "A Coruña", 43.37, -8.40))),

    Market("pl", "Poland", "PLN", "city",
           (49.0, 55.0, 14.0, 24.5), _r(
        ("pl-warszawa", "Warszawa", 52.23, 21.01),
        ("pl-krakow", "Kraków", 50.06, 19.94),
        ("pl-lodz", "Łódź", 51.76, 19.46),
        ("pl-wroclaw", "Wrocław", 51.11, 17.03),
        ("pl-poznan", "Poznań", 52.41, 16.93),
        ("pl-gdansk", "Gdańsk", 54.35, 18.65),
        ("pl-szczecin", "Szczecin", 53.43, 14.55),
        ("pl-lublin", "Lublin", 51.25, 22.57),
        ("pl-katowice", "Katowice", 50.26, 19.02),
        ("pl-bialystok", "Białystok", 53.13, 23.16),
        ("pl-bydgoszcz", "Bydgoszcz", 53.12, 18.00),
        ("pl-rzeszow", "Rzeszów", 50.04, 22.00))),

    Market("it", "Italy", "EUR", "metro region",
           (36.5, 47.2, 6.5, 18.6), _r(
        ("it-rom", "Rom", 41.90, 12.50),
        ("it-milano", "Milano", 45.46, 9.19),
        ("it-neapel", "Neapel", 40.85, 14.27),
        ("it-turin", "Turin", 45.07, 7.69),
        ("it-bologna", "Bologna", 44.49, 11.34),
        ("it-florens", "Florens", 43.77, 11.26),
        ("it-genua", "Genua", 44.41, 8.93),
        ("it-venedig", "Venedig", 45.44, 12.33),
        ("it-verona", "Verona", 45.44, 10.99),
        ("it-bari", "Bari", 41.13, 16.87),
        ("it-palermo", "Palermo", 38.12, 13.36),
        ("it-catania", "Catania", 37.50, 15.09))),

    Market("nl", "Netherlands", "EUR", "city",
           (50.7, 53.6, 3.3, 7.2), _r(
        ("nl-amsterdam", "Amsterdam", 52.37, 4.90),
        ("nl-rotterdam", "Rotterdam", 51.92, 4.48),
        ("nl-haag", "Haag", 52.08, 4.31),
        ("nl-utrecht", "Utrecht", 52.09, 5.12),
        ("nl-eindhoven", "Eindhoven", 51.44, 5.48),
        ("nl-groningen", "Groningen", 53.22, 6.57),
        ("nl-tilburg", "Tilburg", 51.56, 5.09),
        ("nl-almere", "Almere", 52.37, 5.22),
        ("nl-breda", "Breda", 51.59, 4.78),
        ("nl-nijmegen", "Nijmegen", 51.84, 5.85))),

    Market("be", "Belgium", "EUR", "city",
           (49.5, 51.5, 2.5, 6.4), _r(
        ("be-bryssel", "Bryssel", 50.85, 4.35),
        ("be-antwerpen", "Antwerpen", 51.22, 4.40),
        ("be-gent", "Gent", 51.05, 3.72),
        ("be-charleroi", "Charleroi", 50.41, 4.44),
        ("be-liege", "Liège", 50.63, 5.57),
        ("be-brygge", "Brygge", 51.21, 3.22),
        ("be-namur", "Namur", 50.47, 4.87),
        ("be-leuven", "Leuven", 50.88, 4.70))),

    Market("at", "Austria", "EUR", "city",
           (46.4, 49.0, 9.5, 17.2), _r(
        ("at-wien", "Wien", 48.21, 16.37),
        ("at-graz", "Graz", 47.07, 15.44),
        ("at-linz", "Linz", 48.31, 14.29),
        ("at-salzburg", "Salzburg", 47.81, 13.06),
        ("at-innsbruck", "Innsbruck", 47.27, 11.39),
        ("at-klagenfurt", "Klagenfurt", 46.62, 14.31),
        ("at-stpolten", "St. Pölten", 48.20, 15.62))),

    Market("pt", "Portugal", "EUR", "city",
           (36.9, 42.2, -9.6, -6.2), _r(
        ("pt-lissabon", "Lissabon", 38.72, -9.14),
        ("pt-porto", "Porto", 41.15, -8.61),
        ("pt-braga", "Braga", 41.55, -8.42),
        ("pt-coimbra", "Coimbra", 40.21, -8.42),
        ("pt-setubal", "Setúbal", 38.52, -8.89),
        ("pt-aveiro", "Aveiro", 40.64, -8.65),
        ("pt-faro", "Faro", 37.02, -7.93))),

    Market("dk", "Denmark", "DKK", "city",
           (54.5, 57.8, 8.0, 12.7), _r(
        ("dk-kopenhamn", "Köpenhamn", 55.68, 12.57),
        ("dk-arhus", "Århus", 56.16, 10.20),
        ("dk-odense", "Odense", 55.40, 10.39),
        ("dk-aalborg", "Aalborg", 57.05, 9.92),
        ("dk-esbjerg", "Esbjerg", 55.47, 8.45),
        ("dk-randers", "Randers", 56.46, 10.04))),

    Market("fi", "Finland", "EUR", "city",
           (59.8, 66.0, 21.0, 28.0), _r(
        ("fi-helsingfors", "Helsingfors", 60.17, 24.94),
        ("fi-esbo", "Esbo", 60.21, 24.66),
        ("fi-tammerfors", "Tammerfors", 61.50, 23.76),
        ("fi-vanda", "Vanda", 60.29, 25.04),
        ("fi-abo", "Åbo", 60.45, 22.27),
        ("fi-uleaborg", "Uleåborg", 65.01, 25.47))),

    Market("no", "Norway", "NOK", "city",
           (57.9, 70.0, 4.8, 20.0), _r(
        ("no-oslo", "Oslo", 59.91, 10.75),
        ("no-bergen", "Bergen", 60.39, 5.32),
        ("no-trondheim", "Trondheim", 63.43, 10.40),
        ("no-stavanger", "Stavanger", 58.97, 5.73),
        ("no-drammen", "Drammen", 59.74, 10.20),
        ("no-tromso", "Tromsø", 69.65, 18.96))),

    Market("ie", "Ireland", "EUR", "city",
           (51.4, 55.4, -10.5, -5.9), _r(
        ("ie-dublin", "Dublin", 53.35, -6.26),
        ("ie-cork", "Cork", 51.90, -8.47),
        ("ie-limerick", "Limerick", 52.66, -8.63),
        ("ie-galway", "Galway", 53.27, -9.05),
        ("ie-waterford", "Waterford", 52.26, -7.11))),

    Market("cz", "Czechia", "CZK", "city",
           (48.5, 51.1, 12.0, 18.9), _r(
        ("cz-prag", "Prag", 50.08, 14.44),
        ("cz-brno", "Brno", 49.20, 16.61),
        ("cz-ostrava", "Ostrava", 49.82, 18.26),
        ("cz-plzen", "Plzeň", 49.75, 13.38),
        ("cz-liberec", "Liberec", 50.77, 15.06),
        ("cz-olomouc", "Olomouc", 49.59, 17.25))),
]}

# Marknadsgrupper för flerlandsfrågor ("Var i Europa ...?").
EU_MARKETS = tuple(m for m in MARKETS if m != "us")
MARKET_GROUPS: dict[str, tuple[str, ...]] = {
    "eu": EU_MARKETS,
    "varlden": tuple(MARKETS),
}
GROUP_BBOX = {"eu": (35.5, 71.0, -11.0, 32.0),
              "varlden": (23.0, 71.0, -126.0, 32.0)}
GROUP_LABEL_SV = {"eu": "Europe", "varlden": "the world"}


def get_market(market_id: str) -> Market:
    m = MARKETS.get(market_id)
    if m is None:
        raise ValueError(f"Unknown market: {market_id}. "
                         f"Available: {', '.join(sorted(MARKETS))}")
    return m


def get_region(market_id: str, region_kod: str) -> tuple:
    m = get_market(market_id)
    for r in m.regions:
        if r[0] == region_kod:
            return r
    raise ValueError(f"Unknown region: {region_kod} in {m.label_en}. "
                     f"The market covers {len(m.regions)} regions "
                     f"in this version.")


def plural_region_label(label: str) -> str:
    """Engelsk plural för regionbenämningen ("municipality" → "municipalities")."""
    return label[:-1] + "ies" if label.endswith("y") else label + "s"


def find_region_by_name(name_lower: str) -> tuple[str, tuple] | None:
    """Sök region över alla marknader. Returnerar (market_id, region)."""
    for m in MARKETS.values():
        for r in m.regions:
            if r[1].lower() == name_lower:
                return m.id, r
    return None


def market_catalog() -> list[dict]:
    return [{"id": m.id, "label_en": m.label_en, "currency": m.currency,
             "region_label_en": m.region_label_en,
             "antal_regioner": len(m.regions),
             "bbox": list(m.bbox), "kalibrerad": m.calibrated}
            for m in MARKETS.values()]
