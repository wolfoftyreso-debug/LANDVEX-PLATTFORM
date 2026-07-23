"""Marknadsmodellen – Sverige är första marknaden, inte hela systemet.

Varje marknad (land) definieras som data: regioner med koordinater,
kartprojektion (bbox), regionbenämning och valuta. Motorerna är
platsagnostiska – samma modell körs överallt; det som skiljer länder
åt är datakällorna i Resolver-kedjan (SCB för Sverige, Destatis/
Eurostat/Census m.fl. i produktionsfasen) och regionlistan här.

Regionlistorna är förstamarknadsfrön: större städer/regioner med
centroidkoordinater. All icke-svensk data är mockad tills lokala
adaptrar kopplas in – data_coverage och konfidens redovisar det
ärligt, precis som för Sverige innan SCB-adaptern fanns.

Gemensam Opportunity Score över länder förutsätter samma normalise-
ring överallt – därför äger signalkatalogen skalorna, inte länderna.
"""
from __future__ import annotations

from dataclasses import dataclass

from .datasources.scb import KOMMUNER


@dataclass(frozen=True)
class Market:
    id: str
    label_sv: str
    currency: str
    region_label_sv: str
    bbox: tuple            # (lat_min, lat_max, lon_min, lon_max)
    regions: tuple         # ((kod, namn, lat, lon), ...)
    calibrated: bool = False   # ekonomischabloner kalibrerade för marknaden?


def _r(*rows):
    return tuple(rows)


MARKETS: dict[str, Market] = {m.id: m for m in [
    Market("se", "Sverige", "SEK", "kommun",
           (55.0, 69.5, 10.5, 24.5), tuple(KOMMUNER), calibrated=True),

    Market("de", "Tyskland", "EUR", "storstadsregion",
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
        ("de-munster", "Münster", 51.96, 7.63))),

    Market("us", "USA", "USD", "storstadsregion",
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
        ("us-charlotte", "Charlotte", 35.23, -80.84))),

    Market("es", "Spanien", "EUR", "region",
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
        ("es-alicante", "Alicante", 38.35, -0.48))),

    Market("pl", "Polen", "PLN", "stad",
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
        ("pl-bialystok", "Białystok", 53.13, 23.16))),

    Market("fr", "Frankrike", "EUR", "storstadsregion",
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
        ("fr-grenoble", "Grenoble", 45.19, 5.72))),
]}

# Marknadsgrupper för flerlandsfrågor ("Var i Europa ...?").
MARKET_GROUPS: dict[str, tuple[str, ...]] = {
    "eu": ("se", "de", "es", "pl", "fr"),
    "varlden": ("se", "de", "es", "pl", "fr", "us"),
}
GROUP_BBOX = {"eu": (35.0, 70.0, -11.0, 26.0),
              "varlden": (23.0, 70.0, -126.0, 26.0)}
GROUP_LABEL_SV = {"eu": "Europa", "varlden": "världen"}


def get_market(market_id: str) -> Market:
    m = MARKETS.get(market_id)
    if m is None:
        raise ValueError(f"Okänd marknad: {market_id}. "
                         f"Tillgängliga: {', '.join(sorted(MARKETS))}")
    return m


def get_region(market_id: str, region_kod: str) -> tuple:
    m = get_market(market_id)
    for r in m.regions:
        if r[0] == region_kod:
            return r
    raise ValueError(f"Okänd region: {region_kod} i {m.label_sv}. "
                     f"Marknaden täcker {len(m.regions)} regioner "
                     f"i denna version.")


def find_region_by_name(name_lower: str) -> tuple[str, tuple] | None:
    """Sök region över alla marknader. Returnerar (market_id, region)."""
    for m in MARKETS.values():
        for r in m.regions:
            if r[1].lower() == name_lower:
                return m.id, r
    return None


def market_catalog() -> list[dict]:
    return [{"id": m.id, "label_sv": m.label_sv, "currency": m.currency,
             "region_label_sv": m.region_label_sv,
             "antal_regioner": len(m.regions),
             "bbox": list(m.bbox), "kalibrerad": m.calibrated}
            for m in MARKETS.values()]
