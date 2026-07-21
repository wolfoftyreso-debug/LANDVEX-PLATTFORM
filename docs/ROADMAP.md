# Baltic Bridge — Roadmap

From the current codebase (Vite + React + shadcn/ui + Supabase, previously an
e-commerce app) to the Phase 1 marketplaces. Each phase ships working software while
preserving the architecture rules in `docs/ARCHITECTURE.md`.

## Phase 0 — Foundation (repurpose the codebase)

- [ ] Establish vision & architecture docs (this change)
- [ ] Remove/retire legacy e-commerce pages, edge functions and tables not relevant
      to the marketplace
- [ ] Introduce module-oriented source layout (`src/modules/<context>/…`) with
      domain/application/infrastructure separation
- [ ] Set up the vertical configuration model (categories, metadata schemas per
      vertical) — construction and automotive as first entries
- [ ] Database migrations for core contexts: identity, companies, verification,
      rfq, offers, orders, reviews
- [ ] RBAC roles: customer, company member, company admin, moderator, platform admin
- [ ] Audit logging for all state-changing actions
- [ ] i18n scaffolding (multi-language) and money type (multi-currency)

## Phase 1a — Construction Marketplace (MVP)

- [ ] Company registration and standardized profile (all profile fields, logo/cover
      via Media module)
- [ ] Permanent SEO-friendly company URLs (`/company/<slug>`) with structured data
- [ ] Company search with country/region/city/category/rating/language filters
- [ ] RFQ flow: customer posts description, images, address, budget, deadline,
      preferred language
- [ ] RFQ matching → companies receive matching RFQs (Notifications module)
- [ ] Offers: companies submit quotations; customer accepts → Order created
- [ ] Messaging between customer and company
- [ ] Order completion → verified customer review (all review dimensions)
- [ ] Verification v1: identity + VAT checks, Bronze/Silver levels
- [ ] Trust Score v1: verification, reviews, response metrics

## Phase 1b — Automotive Marketplace

- [ ] Enable the automotive vertical via configuration (categories, metadata schema:
      VIN, registration number, damage photos, insurance info, completion date)
- [ ] Workshop-specific RFQ intake and quote flow
- [ ] Verification Gold/Platinum levels; visibility boost in search ranking
- [ ] Trust Score v2: dispute history, documentation quality

## Phase 2 — Payments & Logistics

- [ ] Payments module: checkout on accepted offers, escrow-style capture/release,
      payouts, multi-currency
- [ ] Logistics module (independent): transport booking, pickup, tracking, delivery
      confirmation, insurance, labels; first provider integrations
- [ ] Dispute handling in Administration

## Phase 3 — Scale & self-hosting

- [ ] OpenSearch/Elasticsearch-backed search projections
- [ ] Extract high-load modules into services (event contracts already in place)
- [ ] Kubernetes deployment, Infrastructure as Code, full observability stack
- [ ] Analytics module: marketplace health, funnels

## Phase 4+ — New verticals

Enable additional verticals purely through configuration: manufacturing, industrial
suppliers, agriculture, logistics, legal, accounting, healthcare, consultants,
freelancers, property services, cleaning, security, renewable energy, installation
services.

**Definition of done for the architecture:** adding a vertical requires zero changes
to core engine code.
