"""Administrativt register – delstater, provinser, kantoner, län, regioner
och nivån UNDER: kommuner/counties/communes.

Full administrativ granularitet som DATA, frikopplat från marknadens
metroregioner. Nivå 1 är KOMPLETT här (USA 50 delstater, Kanada 13
provinser/territorier, Schweiz 26 kantoner, Tyskland 16 förbundsländer,
Sverige 21 län, Frankrike 13 regioner, Spanien 17 autonoma regioner,
Italien 20 regioner, Danmark 5 regioner, Nederländerna 12 provinser).

Nivå 2 (kommuner: US ~3143 counties, SE 290 kommuner, CH ~2100 communes,
DE ~11000 Gemeinden…) är för stor att bära inline utan att ljuga om
underhållet. Den laddas därför SKARPT från de officiella registren via
`MunicipalRegister` (config-aktiverad: LANDVEX_GEO_URL, injicerbar
transport, ärlig degradering) och faller annars tillbaka på en MÄRKT
seed med de största enheterna per land – coverage redovisas alltid
(`coverage: partial/full`, `official_total`). Aldrig ett register som
låtsas vara komplett.

Rent stdlib.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

from .datasources.faults import OUR_BUGS

US_STATES = (
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"),
    ("DE", "Delaware"), ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"),
    ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"),
    ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"),
    ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"),
    ("MN", "Minnesota"), ("MS", "Mississippi"), ("MO", "Missouri"),
    ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"),
    ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"),
    ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"),
    ("OH", "Ohio"), ("OK", "Oklahoma"), ("OR", "Oregon"),
    ("PA", "Pennsylvania"), ("RI", "Rhode Island"), ("SC", "South Carolina"),
    ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"),
    ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"),
    ("WA", "Washington"), ("WV", "West Virginia"), ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
)

CA_PROVINCES = (
    ("AB", "Alberta"), ("BC", "British Columbia"), ("MB", "Manitoba"),
    ("NB", "New Brunswick"), ("NL", "Newfoundland and Labrador"),
    ("NS", "Nova Scotia"), ("NT", "Northwest Territories"),
    ("NU", "Nunavut"), ("ON", "Ontario"), ("PE", "Prince Edward Island"),
    ("QC", "Quebec"), ("SK", "Saskatchewan"), ("YT", "Yukon"),
)

CH_CANTONS = (
    ("ZH", "Zürich"), ("BE", "Bern"), ("LU", "Luzern"), ("UR", "Uri"),
    ("SZ", "Schwyz"), ("OW", "Obwalden"), ("NW", "Nidwalden"),
    ("GL", "Glarus"), ("ZG", "Zug"), ("FR", "Fribourg"), ("SO", "Solothurn"),
    ("BS", "Basel-Stadt"), ("BL", "Basel-Landschaft"), ("SH", "Schaffhausen"),
    ("AR", "Appenzell Ausserrhoden"), ("AI", "Appenzell Innerrhoden"),
    ("SG", "St. Gallen"), ("GR", "Graubünden"), ("AG", "Aargau"),
    ("TG", "Thurgau"), ("TI", "Ticino"), ("VD", "Vaud"), ("VS", "Valais"),
    ("NE", "Neuchâtel"), ("GE", "Genève"), ("JU", "Jura"),
)

DE_LANDER = (
    ("BW", "Baden-Württemberg"), ("BY", "Bavaria"), ("BE", "Berlin"),
    ("BB", "Brandenburg"), ("HB", "Bremen"), ("HH", "Hamburg"),
    ("HE", "Hesse"), ("MV", "Mecklenburg-Vorpommern"), ("NI", "Lower Saxony"),
    ("NW", "North Rhine-Westphalia"), ("RP", "Rhineland-Palatinate"),
    ("SL", "Saarland"), ("SN", "Saxony"), ("ST", "Saxony-Anhalt"),
    ("SH", "Schleswig-Holstein"), ("TH", "Thuringia"),
)

SE_LAN = (
    ("01", "Stockholm"), ("03", "Uppsala"), ("04", "Södermanland"),
    ("05", "Östergötland"), ("06", "Jönköping"), ("07", "Kronoberg"),
    ("08", "Kalmar"), ("09", "Gotland"), ("10", "Blekinge"), ("12", "Skåne"),
    ("13", "Halland"), ("14", "Västra Götaland"), ("17", "Värmland"),
    ("18", "Örebro"), ("19", "Västmanland"), ("20", "Dalarna"),
    ("21", "Gävleborg"), ("22", "Västernorrland"), ("23", "Jämtland"),
    ("24", "Västerbotten"), ("25", "Norrbotten"),
)

FR_REGIONS = (
    ("ARA", "Auvergne-Rhône-Alpes"), ("BFC", "Bourgogne-Franche-Comté"),
    ("BRE", "Bretagne"), ("CVL", "Centre-Val de Loire"), ("COR", "Corse"),
    ("GES", "Grand Est"), ("HDF", "Hauts-de-France"), ("IDF", "Île-de-France"),
    ("NOR", "Normandie"), ("NAQ", "Nouvelle-Aquitaine"), ("OCC", "Occitanie"),
    ("PDL", "Pays de la Loire"), ("PAC", "Provence-Alpes-Côte d'Azur"),
)

ES_COMMUNITIES = (
    ("AN", "Andalucía"), ("AR", "Aragón"), ("AS", "Asturias"),
    ("IB", "Illes Balears"), ("CN", "Canarias"), ("CB", "Cantabria"),
    ("CL", "Castilla y León"), ("CM", "Castilla-La Mancha"),
    ("CT", "Cataluña"), ("VC", "Comunitat Valenciana"),
    ("EX", "Extremadura"), ("GA", "Galicia"), ("MD", "Madrid"),
    ("MC", "Murcia"), ("NC", "Navarra"), ("PV", "País Vasco"),
    ("RI", "La Rioja"),
)

IT_REGIONS = (
    ("ABR", "Abruzzo"), ("BAS", "Basilicata"), ("CAL", "Calabria"),
    ("CAM", "Campania"), ("EMR", "Emilia-Romagna"),
    ("FVG", "Friuli-Venezia Giulia"), ("LAZ", "Lazio"), ("LIG", "Liguria"),
    ("LOM", "Lombardia"), ("MAR", "Marche"), ("MOL", "Molise"),
    ("PIE", "Piemonte"), ("PUG", "Puglia"), ("SAR", "Sardegna"),
    ("SIC", "Sicilia"), ("TOS", "Toscana"),
    ("TAA", "Trentino-Alto Adige"), ("UMB", "Umbria"),
    ("VDA", "Valle d'Aosta"), ("VEN", "Veneto"),
)

DK_REGIONS = (
    ("84", "Hovedstaden"), ("85", "Sjælland"), ("83", "Syddanmark"),
    ("82", "Midtjylland"), ("81", "Nordjylland"),
)

NL_PROVINCES = (
    ("DR", "Drenthe"), ("FL", "Flevoland"), ("FR", "Friesland"),
    ("GE", "Gelderland"), ("GR", "Groningen"), ("LI", "Limburg"),
    ("NB", "Noord-Brabant"), ("NH", "Noord-Holland"), ("OV", "Overijssel"),
    ("UT", "Utrecht"), ("ZE", "Zeeland"), ("ZH", "Zuid-Holland"),
)


NO_COUNTIES = (
    ("03", "Oslo"), ("11", "Rogaland"), ("15", "Møre og Romsdal"),
    ("18", "Nordland"), ("31", "Østfold"), ("32", "Akershus"),
    ("33", "Buskerud"), ("34", "Innlandet"), ("39", "Vestfold"),
    ("40", "Telemark"), ("42", "Agder"), ("46", "Vestland"),
    ("50", "Trøndelag"), ("55", "Troms"), ("56", "Finnmark"),
)

FI_REGIONS = (
    ("01", "Uusimaa"), ("02", "Southwest Finland"), ("04", "Satakunta"),
    ("05", "Kanta-Häme"), ("06", "Pirkanmaa"), ("07", "Päijät-Häme"),
    ("08", "Kymenlaakso"), ("09", "South Karelia"), ("10", "South Savo"),
    ("11", "North Savo"), ("12", "North Karelia"), ("13", "Central Finland"),
    ("14", "South Ostrobothnia"), ("15", "Ostrobothnia"),
    ("16", "Central Ostrobothnia"), ("17", "North Ostrobothnia"),
    ("18", "Kainuu"), ("19", "Lapland"), ("21", "Åland"),
)

AT_STATES = (
    ("1", "Burgenland"), ("2", "Carinthia"), ("3", "Lower Austria"),
    ("4", "Upper Austria"), ("5", "Salzburg"), ("6", "Styria"),
    ("7", "Tyrol"), ("8", "Vorarlberg"), ("9", "Vienna"),
)

BE_REGIONS = (
    ("BRU", "Brussels-Capital"), ("VLG", "Flanders"), ("WAL", "Wallonia"),
)

IE_REGIONS = (
    ("EM", "Eastern and Midland"), ("NW", "Northern and Western"),
    ("SO", "Southern"),
)

PT_REGIONS = (
    ("N", "Norte"), ("C", "Centro"), ("LX", "Área Metropolitana de Lisboa"),
    ("ALT", "Alentejo"), ("ALG", "Algarve"), ("AC", "Açores"),
    ("MA", "Madeira"),
)

PL_VOIVODESHIPS = (
    ("02", "Lower Silesian"), ("04", "Kuyavian-Pomeranian"), ("06", "Lublin"),
    ("08", "Lubusz"), ("10", "Łódź"), ("12", "Lesser Poland"),
    ("14", "Masovian"), ("16", "Opole"), ("18", "Subcarpathian"),
    ("20", "Podlaskie"), ("22", "Pomeranian"), ("24", "Silesian"),
    ("26", "Świętokrzyskie"), ("28", "Warmian-Masurian"),
    ("30", "Greater Poland"), ("32", "West Pomeranian"),
)

CZ_REGIONS = (
    ("PHA", "Prague"), ("STC", "Central Bohemian"), ("JHC", "South Bohemian"),
    ("PLK", "Plzeň"), ("KVK", "Karlovy Vary"), ("ULK", "Ústí nad Labem"),
    ("LBK", "Liberec"), ("HKK", "Hradec Králové"), ("PAK", "Pardubice"),
    ("VYS", "Vysočina"), ("JHM", "South Moravian"), ("OLK", "Olomouc"),
    ("ZLK", "Zlín"), ("MSK", "Moravian-Silesian"),
)

# country → nivå-1-register + officiellt nivå-2-register (namn + total).
ADMIN_LEVELS: dict[str, dict] = {
    "us": {"level_en": "state", "units": US_STATES,
           "sub_level": "county", "sub_register": "US Census FIPS",
           "sub_official_total": 3143},
    "ca": {"level_en": "province/territory", "units": CA_PROVINCES,
           "sub_level": "census subdivision (municipality)",
           "sub_register": "StatCan SGC", "sub_official_total": 5161},
    "ch": {"level_en": "canton", "units": CH_CANTONS,
           "sub_level": "commune", "sub_register": "Swiss BFS-Nr",
           "sub_official_total": 2131},
    "de": {"level_en": "federal state (Land)", "units": DE_LANDER,
           "sub_level": "Gemeinde", "sub_register": "Destatis AGS",
           "sub_official_total": 10786},
    "se": {"level_en": "county (län)", "units": SE_LAN,
           "sub_level": "municipality (kommun)",
           "sub_register": "SCB kommunkod", "sub_official_total": 290},
    "fr": {"level_en": "region", "units": FR_REGIONS,
           "sub_level": "commune", "sub_register": "INSEE COG",
           "sub_official_total": 34955},
    "es": {"level_en": "autonomous community", "units": ES_COMMUNITIES,
           "sub_level": "municipio", "sub_register": "INE código",
           "sub_official_total": 8131},
    "it": {"level_en": "region", "units": IT_REGIONS,
           "sub_level": "comune", "sub_register": "ISTAT codice",
           "sub_official_total": 7896},
    "dk": {"level_en": "region", "units": DK_REGIONS,
           "sub_level": "kommune", "sub_register": "Danmarks Statistik",
           "sub_official_total": 98},
    "nl": {"level_en": "province", "units": NL_PROVINCES,
           "sub_level": "gemeente", "sub_register": "CBS code",
           "sub_official_total": 342},
    "no": {"level_en": "county (fylke)", "units": NO_COUNTIES,
           "sub_level": "municipality (kommune)", "sub_register": "SSB kommunenummer",
           "sub_official_total": 357},
    "fi": {"level_en": "region (maakunta)", "units": FI_REGIONS,
           "sub_level": "municipality (kunta)", "sub_register": "Tilastokeskus",
           "sub_official_total": 309},
    "at": {"level_en": "federal state (Land)", "units": AT_STATES,
           "sub_level": "Gemeinde", "sub_register": "Statistik Austria GKZ",
           "sub_official_total": 2093},
    "be": {"level_en": "region", "units": BE_REGIONS,
           "sub_level": "commune/gemeente", "sub_register": "Statbel NIS",
           "sub_official_total": 581},
    "ie": {"level_en": "NUTS-2 region", "units": IE_REGIONS,
           "sub_level": "local electoral area", "sub_register": "CSO",
           "sub_official_total": 166},
    "pt": {"level_en": "region", "units": PT_REGIONS,
           "sub_level": "município", "sub_register": "INE Portugal DICOFRE",
           "sub_official_total": 308},
    "pl": {"level_en": "voivodeship", "units": PL_VOIVODESHIPS,
           "sub_level": "gmina", "sub_register": "GUS TERYT",
           "sub_official_total": 2477},
    "cz": {"level_en": "region (kraj)", "units": CZ_REGIONS,
           "sub_level": "obec", "sub_register": "ČSÚ",
           "sub_official_total": 6254},
}

# ── Nivå 2: seed (största enheterna, MÄRKT partiell) ─────────────────────
# {country: ((code, name, parent_level1_code), …)} – koder ur de officiella
# registren (SCB kommunkod, Census FIPS, StatCan SGC). Seed = demonstration
# och fallback; det kompletta registret laddas via MunicipalRegister.
MUNICIPAL_SEED: dict[str, tuple[tuple[str, str, str], ...]] = {
    "se": (
        ("0180", "Stockholm", "01"), ("1480", "Göteborg", "14"),
        ("1280", "Malmö", "12"), ("0380", "Uppsala", "03"),
        ("0580", "Linköping", "05"), ("1880", "Örebro", "18"),
        ("1980", "Västerås", "19"), ("1283", "Helsingborg", "12"),
        ("0581", "Norrköping", "05"), ("0680", "Jönköping", "06"),
        ("2480", "Umeå", "24"), ("1281", "Lund", "12"),
        ("1490", "Borås", "14"), ("2180", "Gävle", "21"),
        ("0484", "Eskilstuna", "04"), ("0181", "Södertälje", "01"),
        ("1780", "Karlstad", "17"), ("0780", "Växjö", "07"),
        ("1380", "Halmstad", "13"), ("2281", "Sundsvall", "22"),
        ("2580", "Luleå", "25"), ("1488", "Trollhättan", "14"),
        ("2380", "Östersund", "23"), ("2081", "Borlänge", "20"),
        ("0880", "Kalmar", "08"), ("2080", "Falun", "20"),
        ("1290", "Kristianstad", "12"), ("1080", "Karlskrona", "10"),
        ("0980", "Gotland", "09"),
    ),
    "us": (
        ("06037", "Los Angeles County", "CA"), ("17031", "Cook County", "IL"),
        ("48201", "Harris County", "TX"), ("04013", "Maricopa County", "AZ"),
        ("06073", "San Diego County", "CA"), ("06059", "Orange County", "CA"),
        ("12086", "Miami-Dade County", "FL"), ("48113", "Dallas County", "TX"),
        ("36047", "Kings County", "NY"), ("06065", "Riverside County", "CA"),
        ("32003", "Clark County", "NV"), ("53033", "King County", "WA"),
        ("36081", "Queens County", "NY"), ("48439", "Tarrant County", "TX"),
        ("48029", "Bexar County", "TX"), ("12011", "Broward County", "FL"),
        ("06085", "Santa Clara County", "CA"), ("26163", "Wayne County", "MI"),
        ("06001", "Alameda County", "CA"), ("25017", "Middlesex County", "MA"),
    ),
    "ca": (
        ("3520005", "Toronto", "ON"), ("2466023", "Montréal", "QC"),
        ("4806016", "Calgary", "AB"), ("3506008", "Ottawa", "ON"),
        ("4811061", "Edmonton", "AB"), ("4611040", "Winnipeg", "MB"),
        ("3521005", "Mississauga", "ON"), ("5915022", "Vancouver", "BC"),
        ("3521010", "Brampton", "ON"), ("3525005", "Hamilton", "ON"),
    ),
}



# ── Nivå 3: postnummer (zipcodes/postcodes/Postleitzahlen) ──────────────
# Postnummer är INTE administrativa enheter – de är postens leveransområden
# och följer sällan kommungränser. De bärs därför som en EGEN nivå med sitt
# eget register per land, aldrig som "en mindre kommun". Formatet dokumenteras
# så en klient kan validera indata utan att gissa.
POSTAL_REGISTERS: dict[str, dict] = {
    "us": {"label_en": "ZIP Code", "register": "USPS / Census ZCTA",
           "format": "5 digits (optionally +4)", "example": "94103",
           "official_total": 41692},
    "ca": {"label_en": "Postal code", "register": "Canada Post",
           "format": "A1A 1A1 (forward sortation area + local unit)",
           "example": "M5V 3L9", "official_total": 876445},
    "se": {"label_en": "Postnummer", "register": "PostNord",
           "format": "5 digits (NNN NN)", "example": "702 25",
           "official_total": 16000},
    "de": {"label_en": "Postleitzahl", "register": "Deutsche Post",
           "format": "5 digits", "example": "10115", "official_total": 8200},
    "ch": {"label_en": "PLZ", "register": "Swiss Post",
           "format": "4 digits", "example": "8001", "official_total": 4150},
    "fr": {"label_en": "Code postal", "register": "La Poste",
           "format": "5 digits", "example": "75001", "official_total": 6300},
    "es": {"label_en": "Código postal", "register": "Correos",
           "format": "5 digits (first 2 = province)", "example": "28001",
           "official_total": 11752},
    "it": {"label_en": "CAP", "register": "Poste Italiane",
           "format": "5 digits", "example": "00184", "official_total": 10750},
    "nl": {"label_en": "Postcode", "register": "PostNL",
           "format": "1234 AB", "example": "1011 AB", "official_total": 461000},
    "dk": {"label_en": "Postnummer", "register": "PostNord Danmark",
           "format": "4 digits", "example": "1050", "official_total": 1200},
    "no": {"label_en": "Postnummer", "register": "Posten Norge",
           "format": "4 digits", "example": "0150", "official_total": 5100},
    "fi": {"label_en": "Postinumero", "register": "Posti",
           "format": "5 digits", "example": "00100", "official_total": 3000},
    "at": {"label_en": "Postleitzahl", "register": "Österreichische Post",
           "format": "4 digits", "example": "1010", "official_total": 2900},
    "be": {"label_en": "Postcode", "register": "bpost",
           "format": "4 digits", "example": "1000", "official_total": 1150},
    "ie": {"label_en": "Eircode", "register": "An Post / Eircode",
           "format": "A65 F4E2 (routing key + unique identifier)",
           "example": "D02 X285", "official_total": 2200000},
    "pt": {"label_en": "Código postal", "register": "CTT",
           "format": "1234-567", "example": "1000-001",
           "official_total": 320000},
    "pl": {"label_en": "Kod pocztowy", "register": "Poczta Polska",
           "format": "12-345", "example": "00-001", "official_total": 26000},
    "cz": {"label_en": "PSČ", "register": "Česká pošta",
           "format": "123 45", "example": "110 00", "official_total": 2700},
}


def postal_register(country: str) -> dict:
    """Postnummersystemet för ett land – format, register och omfattning.

    Själva listan laddas från postoperatörens register via
    `MunicipalRegister`-mönstret (LANDVEX_GEO_URL/{country}-postal.json);
    ingen postnummerlista bärs inline, och ingen påhittas.
    """
    reg = POSTAL_REGISTERS.get(country)
    if reg is None:
        raise ValueError(f"no postal register for country: {country}")
    return {"country": country, "level": 3, **reg, "coverage": "register_only",
            "note": "Postal areas are delivery zones, not administrative "
                    "units — they do not nest cleanly inside municipalities. "
                    "The list loads from the postal operator's register; "
                    "none are carried inline and none are invented."}


def _http_transport(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "landvex/admin"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


class MunicipalRegister:
    """Nivå 2 skarpt: laddar kompletta kommunregister från en konfigurerad
    källa (samma adapter-mönster som Kolada/SvK).

    Kontrakt: LANDVEX_GEO_URL pekar på en bas som serverar
    {base}/{country}.json = [{"code","name","parent"}, …] (speglad från de
    officiella registren: Census FIPS, SCB, StatCan SGC, INSEE COG…).
    Ej ansluten eller fel → ärlig degradering till MUNICIPAL_SEED, märkt
    coverage="partial". Hittar aldrig på enheter.
    """

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 8.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_GEO_URL", "")).rstrip("/")
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def fetch(self, country: str) -> list[dict] | None:
        """Komplett nivå-2-lista för ett land, eller None (ej ansluten/fel)."""
        if not self.connected:
            return None
        try:
            raw = json.loads(self._transport(
                f"{self.base_url}/{country}.json", self.timeout))
        except OUR_BUGS:
            # Det här är en nätadapter — exakt det slags kod faults.py
            # skrevs för — men den bor utanför engine/datasources/ och
            # undgick därför svepet. Ett stavfel här lästes som "källan
            # är nere" och degraderade tyst till fröregistret.
            raise
        except Exception:  # noqa: BLE001 - ärlig degradering
            return None
        if not isinstance(raw, list):
            return None
        out = []
        for row in raw:
            if isinstance(row, dict) and row.get("code") and row.get("name"):
                out.append({"code": str(row["code"]), "name": str(row["name"]),
                            "parent": str(row.get("parent", ""))})
        return out or None

    def status(self) -> dict:
        return {"name": "geo", "connected": self.connected,
                "base_url": self.base_url or None,
                "seeded_countries": sorted(MUNICIPAL_SEED)}


def admin_countries() -> list[dict]:
    """Vilka länder som har ett administrativt register + räkning per nivå."""
    return [{"country": c, "level_en": d["level_en"], "count": len(d["units"]),
             "sub_level": d["sub_level"], "sub_register": d["sub_register"],
             "sub_official_total": d["sub_official_total"],
             "sub_seeded": len(MUNICIPAL_SEED.get(c, ())),
             "postal_level": (POSTAL_REGISTERS.get(c) or {}).get("label_en")}
            for c, d in ADMIN_LEVELS.items()]


def admin_units(country: str, level: int = 1, parent: str = "",
                register: MunicipalRegister | None = None) -> dict:
    """Administrativa enheter för ett land.

    level=1: komplett nivå 1 (delstater/kantoner/län/regioner).
    level=2: kommunnivån – skarpt via MunicipalRegister om ansluten
    (coverage="full"), annars märkt seed (coverage="partial",
    official_total redovisat). parent filtrerar på nivå-1-kod.
    """
    d = ADMIN_LEVELS.get(country)
    if d is None:
        raise ValueError(f"no administrative register for country: {country}")
    if level == 1:
        return {"country": country, "level": 1, "level_en": d["level_en"],
                "count": len(d["units"]), "coverage": "full",
                "units": [{"code": c, "name": n} for c, n in d["units"]],
                "sub_level": d["sub_level"],
                "sub_register": d["sub_register"]}
    if level == 3:
        return postal_register(country)
    if level != 2:
        raise ValueError("level must be 1 (regions), 2 (municipalities) "
                         "or 3 (postal areas)")

    reg = register or MunicipalRegister()
    live = reg.fetch(country)
    if live is not None:
        units, coverage, source = live, "full", "official register (live)"
    else:
        units = [{"code": c, "name": n, "parent": p}
                 for c, n, p in MUNICIPAL_SEED.get(country, ())]
        coverage, source = "partial", "seed (largest units)"
    if parent:
        units = [u for u in units if u.get("parent") == parent]
    return {"country": country, "level": 2, "level_en": d["sub_level"],
            "register": d["sub_register"], "coverage": coverage,
            "source": source, "official_total": d["sub_official_total"],
            "count": len(units), "parent": parent or None, "units": units,
            "note": ("Complete list loads live from the official register "
                     "once LANDVEX_GEO_URL is set; a partial seed is never "
                     "presented as complete." if coverage == "partial"
                     else "Loaded live from the configured register mirror.")}
