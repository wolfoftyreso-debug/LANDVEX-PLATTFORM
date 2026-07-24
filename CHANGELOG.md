# Changelog

Formatet följer [Keep a Changelog](https://keepachangelog.com/); semantisk versionering.

## [1.0.0] — 2026-07-24
Första fristående releasen — utlyft ur monorepo till eget, rent repo.

- Beroendefri motorkärna (`engine/`, stdlib) + dubbla API-lager (FastAPI +
  stdlib-server), låsta lika av kontraktstest.
- 6 beslutslager (Opportunity Score, Opportunity Intelligence, Risk
  Intelligence/Business Signals, Workforce, Installed Base, Intelligence Map).
- 35 marknader / 344 regioner (alla 50 US-delstater, alla 27 EU-länder).
- Datakällor via Resolver-kedja: SCB live; permits/places/programs/quiXzoom
  kod-klara, aktiveras per env-variabel; ärlig degradering till mock.
- Självförsörjande portal med intro-hero. 24 testsviter, självupptäckande CI.
