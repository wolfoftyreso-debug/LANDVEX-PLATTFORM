"""Vems fel var det — omvärldens eller vårt?

En datakälla MÅSTE tåla att omvärlden fallerar. Nätet går ner, ett API
svarar 500, ett fält saknas i en payload. Då är rätt beteende att pausa
källan och låta Resolvern falla vidare till mock, ärligt märkt.

Men `except Exception` skiljer inte på omvärlden och oss. Ett stavfel i
vår egen kod ser ut precis som en trasig uppkoppling, och blir därför
tyst nedgradering till mock i stället för ett fel någon rättar.

Det har redan hänt i det här projektet: `LivabilitySource` anropade
`locator.nearest()` när klassen bara har `locate()`. AttributeError
fångades av samma skyddsnät som nätverksfel. Kopplingen SÅG ansluten ut,
proben rapporterade källan som konfigurerad, och den levererade mock —
tills någon läste koden.

Regeln här är smal med flit:

    AttributeError   ett attribut/metod som inte finns
    NameError        ett namn som inte finns
    ImportError      en modul som inte finns
    IndentationError/SyntaxError   kod som inte går att köra

Ingen av dem kan orsakas av vad en server svarar. De är alltid vårt fel
och ska braka, högt och tidigt. Allt annat — OSError, timeouts, HTTP-fel,
JSONDecodeError, ValueError, KeyError, TypeError — kan mycket väl vara
omvärlden, och behandlas som källfel.

TypeError och KeyError ligger medvetet på omvärldens sida: `float(None)`
och `payload["saknas"]` uppstår båda av data vi inte styr över. Att låta
dem braka skulle göra en trasig payload till ett femhundrafel för
användaren, vilket är precis det källpausen finns för att undvika.

Rent stdlib.
"""
from __future__ import annotations

# Fel som ALDRIG kan komma från en server som svarar konstigt.
OUR_BUGS: tuple[type[BaseException], ...] = (
    AttributeError, NameError, ImportError, SyntaxError, IndentationError,
)


def is_our_bug(exc: BaseException) -> bool:
    return isinstance(exc, OUR_BUGS)


class source_fault:
    """Kontexthanterare: svälj omvärldens fel, släpp igenom våra egna.

        with source_fault() as f:
            raw = client.fetch(...)
        if f.failed:
            ...pausa källan...

    Ett programmeringsfel passerar orört och fäller anropet — vilket är
    poängen: det ska märkas medan någon kan rätta det.
    """

    __slots__ = ("error",)

    def __init__(self) -> None:
        self.error: BaseException | None = None

    def __enter__(self) -> "source_fault":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            return False
        if is_our_bug(exc):
            return False              # vårt fel – låt det braka
        self.error = exc
        return True                   # omvärldens fel – svald, källan pausas

    @property
    def failed(self) -> bool:
        return self.error is not None
