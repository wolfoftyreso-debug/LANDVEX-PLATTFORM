"""EN default-resolver — deterministisk, nätfri, märkt mock. Delad.

Sju motorer bar varsin `_DEFAULT_RESOLVER = Resolver([MockSource()])`.
Revisionen samlade dem hit — och prövade först att göra defaulten till
produktionskedjan. Det ÅTERTOGS, med mätning som skäl:

    CI (öppet nät): gap_analysis("bilverkstad", market="se") utan
    resolver tog 72 sekunder och gav OLIKA svar två gånger i rad —
    SCB och Kolada är nyckellösa med default-adresser och därmed
    anslutna så fort nätet är öppet. Determinismtestet föll, och
    varje motoranrop utan resolver hade blivit ett nätanrop.

Regeln som håller är i stället:

  * Motorernas default är MÄRKT SIMULERING — deterministisk, nätfri,
    och sedan revisionen märkt på svaret (`data_coverage`, `kalla`).
    Ett glömt `resolver=` ger ett tal som SÄGER att det är simulerat,
    aldrig ett överraskande nätanrop i en svarsbudget på 700 ms.
  * Den riktiga kedjan är API-LAGRETS ansvar: RESOLVER där bär
    produktionskällorna OCH cachen, och kontraktstestet låser att varje
    marknadsmotor får den uttryckligen.
  * Bakgrundssvep (engine/analysis) som VILL se produktionskedjan
    bygger den själv via `production_resolver()` — de är schemalagda
    jobb utan svarsbudget, och ett svep på ren mock rapporterar
    "inga fynd" och betyder blind.
"""
from __future__ import annotations

from .base import Resolver
from .mock import MockSource

_MOCK: Resolver | None = None
_PROD: Resolver | None = None


def default_resolver() -> Resolver:
    """Motorernas default: märkt mock, aldrig nät. Cachad per process."""
    global _MOCK
    if _MOCK is None:
        _MOCK = Resolver([MockSource()])
    return _MOCK


def production_resolver() -> Resolver:
    """Produktionskällorna + märkt mock — för bakgrundssvep och
    anropare som uttryckligen vill nå nätet. Cachad per process."""
    global _PROD
    if _PROD is None:
        from .adapters import production_sources
        _PROD = Resolver(production_sources() + [MockSource()])
    return _PROD


def reset() -> None:
    """Endast för tester: tvinga omkonstruktion (t.ex. efter env-byte)."""
    global _MOCK, _PROD
    _MOCK = None
    _PROD = None
