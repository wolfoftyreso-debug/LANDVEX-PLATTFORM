"""Vad ett andra oberoende nät faktiskt tillför.

Fler sensorer gör inte ett underlag robustare av sig självt. Tio
mätpunkter på samma väg, från samma myndighet, genom samma
insamlingskedja, faller tillsammans när kedjan gör det — och tio
samstämmiga tal från ett trasigt system ser precis ut som tio
samstämmiga tal från ett fungerande.

Det som gör ett underlag robust är att ett OBEROENDE nät säger samma
sak. Trafikverkets slingor och Digitraffics slingor mäter samma sorts
sak men drivs av olika myndigheter i olika länder — de är oberoende. Två
slingor på samma väg är det inte.

**Nätet, inte klassen, avgör oberoendet.** Den skillnaden var borta i
första versionen: koden räknade unika `sensor_class`, så exemplet ovan —
modulens eget — blev EN källa, och taket "a single network cannot
corroborate itself" slog till på just det par som skulle visa vad
oberoende betyder. Källor bär därför ett valfritt `network`, och två
leverantörer inom samma klass räknas som två nät.

Att de delar MODALITET räknas fortfarande emot dem: två fordonsräknare
kan bära samma systematiska fel, och paret når därför `moderate` men
aldrig `strong`. Det starkaste underlaget är fortfarande två nät som
mäter olika fysiska storheter och ändå pekar åt samma håll.

Modulen räknar ut tre saker om ett påstående:

    independent_sources   hur många oberoende nät som säger något
    agreement             om de säger samma sak, när det går att jämföra
    strength              en BAND, aldrig en procent

`strength` är medvetet ett band. En siffra som "84 % säkert" inbjuder
till att multipliceras vidare i kalkyler den inte tål — det är samma fel
som Daily Brief undviker med sin confidence-band, och det finns ingen
anledning att göra om det här.

En enda källa får ALDRIG nå högsta bandet, hur väl den än stämmer med
sig själv. Det är hela poängen: självbekräftelse är inte bekräftelse.

Rent stdlib.
"""
from __future__ import annotations

# Vad en sensorklass i grunden mäter. Två klasser som mäter samma
# storhet genom samma sorts kedja bekräftar varandra svagare än två som
# mäter olika saker och råkar peka åt samma håll.
MODALITY: dict[str, str] = {
    "road_flow": "vehicle_count",
    "public_transport": "vehicle_position",
    "vessel_traffic": "vehicle_position",
    "parking_occupancy": "vehicle_count",
    "mobility_flow": "device_presence",
    "air_quality": "chemistry",
    "weather": "atmosphere",
    "water_level": "hydrology",
    "seismic": "ground_motion",
    "grid_telemetry": "energy",
    "district_heating": "energy",
    "building_meter": "energy",
    "water_utility": "flow_volume",
    "waste_volume": "mass",
    "earth_observation": "imagery",
    "field_observation": "imagery",
    "construction_activity": "machine_telemetry",
}

# "conflicting" är inte ett steg på skalan utan ett eget utfall: det
# uppstår när källorna säger emot varandra, oavsett hur många de är.
BANDS = (
    (0.75, "strong", "Independent networks of different kinds agree."),
    (0.50, "moderate", "More than one source, but they share a modality "
                       "or do not fully agree."),
    (0.25, "weak", "Effectively a single line of evidence."),
    (0.0, "none", "Nothing corroborates this."),
)

# Ett påstående som bara vilar på en källa får aldrig gå högre än detta,
# hur perfekt den källan än stämmer med sig själv.
SINGLE_SOURCE_CEILING = "weak"

# Under den här samstämmigheten SÄGER källorna emot varandra. Det är inte
# ett svagt stöd — det är ett fynd i sig, och att låta det passera som
# "strong" bara för att källorna är oberoende vore att räkna oenighet som
# bekräftelse. Två nät som pekar åt olika håll är sämre underlag än ett
# ensamt nät, eftersom minst ett av dem har fel och man inte vet vilket.
CONFLICT_BELOW = 0.50


def _agreement(varden: list[float]) -> float | None:
    """Hur nära varandra oberoende mätningar ligger, 0–1.

    Variationskoefficient omvänd: identiska värden ger 1.0, spridning
    drar mot 0. None när det inte finns två tal att jämföra — vilket är
    ett annat svar än "de är oense", och de får inte blandas ihop.
    """
    tal = [float(v) for v in varden if isinstance(v, (int, float))]
    if len(tal) < 2:
        return None
    m = sum(tal) / len(tal)
    if m == 0:
        return 1.0 if all(t == 0 for t in tal) else 0.0
    spridning = (sum((t - m) ** 2 for t in tal) / len(tal)) ** 0.5
    cv = abs(spridning / m)
    return max(0.0, min(1.0, 1.0 - cv))


def assess(sources: list[dict]) -> dict:
    """Hur väl underbyggt ett påstående är.

    `sources` = [{"sensor_class": .., "network": <valfritt id>,
                  "value": <valfritt tal>, "measured": bool}].

    Ett värde är frivilligt: två nät kan bekräfta ATT något hände utan
    att mäta samma storhet. `network` är också frivilligt och faller
    tillbaka på klassen — men två leverantörer inom samma klass
    (Trafikverket och Digitraffic) räknas som två nät bara om de säger
    vilka de är.
    """
    matta = [s for s in sources if s.get("measured", True)]
    klasser = [s.get("sensor_class", "") for s in matta]
    modaliteter = {MODALITY.get(k, k or "unknown") for k in klasser}
    # Oberoende räknas på NÄTET, inte på klassen. Utan `network` faller
    # varje källa tillbaka på sin klass, så ett anrop som inte känner
    # till fältet får exakt samma tal som förut.
    #
    # Skillnaden är inte teoretisk: modulens eget exempel ovan —
    # Trafikverkets slingor och Digitraffics — har BÅDA
    # sensor_class="road_flow". Med klassräkning blev de en enda källa
    # och taket "a single network cannot corroborate itself" slog till på
    # just det par docstringen valt som förebild för oberoende.
    nat = [s.get("network") or s.get("sensor_class", "") for s in matta]
    n_oberoende = len(set(nat))
    n_modaliteter = len(modaliteter)

    varden = [s["value"] for s in matta if "value" in s]
    samstammighet = _agreement(varden)

    # Poängen: oberoende väger tyngst, olika modalitet väger näst,
    # och samstämmighet räknas bara när den går att mäta.
    poang = 0.0
    if n_oberoende >= 2:
        poang += 0.45
    if n_oberoende >= 3:
        poang += 0.10
    if n_modaliteter >= 2:
        poang += 0.25
    if samstammighet is not None:
        poang += 0.20 * samstammighet
    elif n_oberoende >= 2:
        # Två nät som säger ATT något hände, utan jämförbara tal, är
        # fortfarande mer än ett — men mindre än två som stämmer.
        poang += 0.10
    poang = round(min(1.0, poang), 4)

    band = next(b for gr, b, _ in BANDS if poang >= gr)
    varfor = next(t for gr, _, t in BANDS if poang >= gr)
    takad = False

    # Oenighet är ett fynd, inte ett svagt stöd.
    konflikt = samstammighet is not None and samstammighet < CONFLICT_BELOW
    if konflikt:
        band, poang = "conflicting", round(min(poang, 0.25), 4)
        varfor = ("Independent networks disagree. At least one of them is "
                  "wrong and it is not knowable from here which — that is "
                  "a weaker basis than a single source, not a stronger "
                  "one, and it is worth looking at on its own.")
    elif n_oberoende < 2 and band in ("strong", "moderate"):
        band, takad = SINGLE_SOURCE_CEILING, True
        varfor = ("A single network cannot corroborate itself, however "
                  "well it agrees with its own readings.")

    return {
        "independent_sources": n_oberoende,
        "networks": sorted(set(nat)),
        "sensor_classes": sorted(set(klasser)),
        "modalities": sorted(modaliteter),
        "agreement": samstammighet,
        "score": poang,
        "strength": band,
        "why_en": varfor,
        "capped_by_single_source": takad,
        "conflicting": konflikt,
        "not_a_probability_en": (
            "A band, not a percentage. A number like '84% certain' invites "
            "being multiplied onward into calculations it cannot carry — "
            "the same trap the Daily Brief avoids, and there is no reason "
            "to walk into it here."),
        "unmeasured_ignored": len(sources) - len(matta),
    }


def independence(a: str, b: str, *, network_a: str = "",
                 network_b: str = "") -> dict:
    """Är två källor oberoende av varandra?

    Klassen säger VAD som mäts, nätet säger VEM som mäter det. Två
    leverantörer inom samma klass är oberoende av varandra (olika
    myndighet, olika insamlingskedja) men delar modalitet — de kan bära
    samma systematiska fel, och når därför aldrig högsta bandet.
    """
    ma, mb = MODALITY.get(a, "unknown"), MODALITY.get(b, "unknown")
    na, nb = network_a or a, network_b or b
    oberoende = na != nb
    return {
        "a": a, "b": b, "modality_a": ma, "modality_b": mb,
        "network_a": na, "network_b": nb,
        "independent": oberoende,
        "different_modality": ma != mb,
        "why_en": (
            "Different networks measuring different physical quantities. "
            "The strongest kind of corroboration."
            if oberoende and ma != mb else
            "Different networks, but the same physical quantity — they can "
            "still share a systematic error."
            if oberoende else
            "The same network. More points from one network is more of the "
            "same evidence, not a second opinion."),
    }


def catalog() -> dict:
    grupper: dict[str, list[str]] = {}
    for k, m in MODALITY.items():
        grupper.setdefault(m, []).append(k)
    return {
        "modalities": {m: sorted(v) for m, v in sorted(grupper.items())},
        "bands": [{"at_least": g, "band": b, "means_en": t}
                  for g, b, t in BANDS],
        "single_source_ceiling": SINGLE_SOURCE_CEILING,
        "principle_en": (
            "More sensors is not more robust. Ten points on the same road, "
            "from the same authority, through the same collection chain, "
            "fail together when the chain does — and ten agreeing numbers "
            "from a broken system look exactly like ten agreeing numbers "
            "from a working one. What makes a basis robust is an "
            "INDEPENDENT network saying the same thing."),
    }
