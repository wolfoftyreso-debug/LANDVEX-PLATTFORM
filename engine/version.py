"""Motorversion – stämplas i varje rapport och API-svar.

Reproducerbarhet: en sparad rapport bär engine_version + full
signalnedbrytning (värden, källor, kvalitet). Samma version + samma
signalvärden ⇒ samma score. Höj versionen vid varje ändring av
scoring-, risk- eller prognoslogik så att historiska rapporter kan
tolkas korrekt.
"""
# 0.10.0 stod kvar genom hela dissg-skörden — lambda_index, kpi,
# setpoints, scorekit och stats ändrade alla den beräknande logiken,
# medan varje sparad rapport fortsatte stämplas 0.10.0. Två materiellt
# olika motorer under samma stämpel bryter exakt det löfte den här
# filens docstring ger. CHANGELOG, Makefile och docs/aws.md sa redan
# 1.1.0; det var stämpeln som halkat efter. Ett test håller dem lika.
ENGINE_VERSION = "1.1.0"
