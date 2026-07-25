"""Administrativt register – delstater, kantoner, län, kommuner.

Full administrativ granularitet som DATA, frikopplat från marknadens
metroregioner. Här ligger de OFFICIELLA enheterna: USA:s 50 delstater,
Schweiz 26 kantoner, Tysklands 16 förbundsländer, Sveriges 21 län. Nivån
under (kommuner/counties/communes: US ~3143 counties, SE 290 kommuner, CH
~2100 communes) laddas från de officiella registren (US Census FIPS,
SCB kommunkod, Swiss BFS-Nr, Destatis AGS) via samma adapter-mönster –
strukturen bär dem, listorna fylls på skarpt.

Rent data, stdlib.
"""
from __future__ import annotations

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

# country → (level_en, units, municipal_note)
ADMIN_LEVELS: dict[str, dict] = {
    "us": {"level_en": "state", "units": US_STATES,
           "sub_level": "county (~3143) — US Census FIPS"},
    "ch": {"level_en": "canton", "units": CH_CANTONS,
           "sub_level": "commune (~2100) — Swiss BFS-Nr"},
    "de": {"level_en": "federal state (Land)", "units": DE_LANDER,
           "sub_level": "Gemeinde (~11000) — Destatis AGS"},
    "se": {"level_en": "county (län)", "units": SE_LAN,
           "sub_level": "municipality (290) — SCB kommunkod"},
}


def admin_countries() -> list[dict]:
    """Vilka länder som har ett administrativt register + räkning."""
    return [{"country": c, "level_en": d["level_en"], "count": len(d["units"]),
             "sub_level": d["sub_level"]}
            for c, d in ADMIN_LEVELS.items()]


def admin_units(country: str) -> dict:
    """Alla administrativa enheter för ett land."""
    d = ADMIN_LEVELS.get(country)
    if d is None:
        raise ValueError(f"no administrative register for country: {country}")
    return {"country": country, "level_en": d["level_en"],
            "count": len(d["units"]),
            "units": [{"code": c, "name": n} for c, n in d["units"]],
            "sub_level": d["sub_level"],
            "note": "Sub-municipal units load from the official register via the "
                    "adapter pattern; this level is complete."}
