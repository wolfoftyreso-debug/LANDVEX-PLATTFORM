"""Motorversion – stämplas i varje rapport och API-svar.

Reproducerbarhet: en sparad rapport bär engine_version + full
signalnedbrytning (värden, källor, kvalitet). Samma version + samma
signalvärden ⇒ samma score. Höj versionen vid varje ändring av
scoring-, risk- eller prognoslogik så att historiska rapporter kan
tolkas korrekt.
"""
ENGINE_VERSION = "0.9.0"
