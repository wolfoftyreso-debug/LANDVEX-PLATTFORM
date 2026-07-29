"""EN default-resolver — produktionskedjan plus märkt mock, delad.

Fyra motorer bar varsin `_DEFAULT_RESOLVER = Resolver([MockSource()])`.
Det är fällan analysis.py dokumenterade och undvek lokalt: en anropare
som glömmer `resolver=` fick ett 100 % simulerat tal, och i motorer utan
täckningsfält sa ingenting i svaret att så var fallet. API-lagren
skickar alltid den riktiga kedjan — fällan gällde interna anropare,
skript och nästa utvecklare.

Defaulten är nu samma sak som den riktiga kedjan: produktionskällor
först (oanslutna adaptrar är `connected=False` och gör NOLL nätanrop,
så en nätfri miljö beter sig exakt som förr), märkt mock sist så att
svaret aldrig blir tomt utan blir ärligt etiketterat.

Cachad per process: `production_sources()` bygger klienter, och en
default som konstruerar om kedjan per anrop hade gjort varje glömt
`resolver=` till en prestandabugg i stället för en ärlighetsbugg.
"""
from __future__ import annotations

from .base import Resolver
from .mock import MockSource

_CACHE: Resolver | None = None


def default_resolver() -> Resolver:
    global _CACHE
    if _CACHE is None:
        from .adapters import production_sources
        _CACHE = Resolver(production_sources() + [MockSource()])
    return _CACHE


def reset() -> None:
    """Endast för tester: tvinga omkonstruktion (t.ex. efter env-byte)."""
    global _CACHE
    _CACHE = None
