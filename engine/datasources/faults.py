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


def unreachable(exc: BaseException | None) -> bool:
    """Betyder felet ONÅBAR värd (nät/policy) snarare än konstigt svar?

    Skillnaden är hela poängen med en probe. En spärrad brandvägg säger
    ingenting om adapterns kvalitet; ett konstigt svar gör det.

    En egen TCP-koll mot värden dög inte: med en utgående proxy LYCKAS
    anslutningen medan hämtningen ändå faller, och då skrevs en spärrad
    brandvägg ned som en trasig adapter. Klassa på felet från det
    VERKLIGA anropet i stället.

    Låg här, inte i en av proberna, eftersom två prober behöver den och
    två kopior av samma regel glider isär — samma skäl som `percentile`
    bor i engine/stats.py.
    """
    import socket
    import urllib.error

    if exc is None:
        return False
    if isinstance(exc, urllib.error.HTTPError):
        # Servern svarade. 404 är ett riktigt svar; 403/407/5xx är inte.
        return exc.code in (403, 407, 502, 503, 504)
    return isinstance(exc, (urllib.error.URLError, socket.timeout, OSError,
                            ConnectionError))


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


class Breaker:
    """Strömbrytare: ETT misslyckande räcker som besked.

    Bodde först i `RegisterProvider`, där den skrevs efter att
    /v1/saturation gjort sextio blockerande HTTPS-anrop i EN request och
    tagit nitton sekunder att svara "vet inte". Sensorkällor har exakt
    samma problem — ett mätvärde per punkt, hundratals punkter — så den
    flyttades hit i stället för att kopieras. En andra kopia av en regel
    är en regel som kommer att glida isär.

    `fetch` returnerar None när källan är nere eller pausad. Våra egna
    buggar går rakt igenom (se OUR_BUGS ovan): en AttributeError i vår
    kod får aldrig se ut som att en myndighet är otillgänglig.
    """

    __slots__ = ("_transport", "timeout", "_retry_after_s", "_clock",
                 "_down_until", "last_error")

    def __init__(self, transport, timeout: float = 10.0,
                 retry_after_s: float = 300.0, clock=None):
        import time as _t
        self._transport = transport
        self.timeout = timeout
        self._retry_after_s = retry_after_s
        self._clock = clock or _t.monotonic
        self._down_until = 0.0
        # Senaste omvärldsfelet. En probe måste kunna skilja "kom aldrig
        # fram" från "kom fram men svaret såg fel ut" — annars skrivs en
        # spärrad brandvägg ned som en trasig adapter.
        self.last_error: BaseException | None = None

    @property
    def down(self) -> bool:
        return self._clock() < self._down_until

    def trip(self) -> None:
        self._down_until = self._clock() + self._retry_after_s

    def reset(self) -> None:
        self._down_until = 0.0

    def fetch(self, *args) -> bytes | None:
        if self.down:
            return None
        try:
            raw = self._transport(*args, self.timeout)
        except OUR_BUGS:
            raise            # vårt fel, inte omvärldens
        except Exception as e:   # noqa: BLE001 – ärlig degradering
            self.last_error = e
            self.trip()
            return None
        self.last_error = None
        self.reset()
        return raw
