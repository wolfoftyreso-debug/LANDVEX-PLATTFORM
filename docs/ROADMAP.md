# Baltic Bridge — Roadmap

From the current codebase (Vite + React + shadcn/ui + Supabase, previously an
e-commerce app) to the Phase 1 marketplaces. Each phase ships working software while
preserving the architecture rules in `docs/ARCHITECTURE.md`.

## Phase 0 — Foundation (repurpose the codebase)

- [x] Establish vision & architecture docs
- [x] Remove/retire legacy e-commerce pages and components (edge functions and
      legacy tables remain to be retired once data is archived)
- [x] Introduce module-oriented source layout (`src/modules/<context>/…`)
- [x] Set up the vertical configuration model (categories in DB, metadata schemas
      per vertical in `src/modules/marketplace/config.ts`) — construction and
      automotive as first entries
- [x] Database migrations for core contexts: companies, verification, rfq,
      offers, orders, reviews, messaging, notifications
- [x] RBAC v1 via RLS policies (customer, company member/owner, admin);
      moderator/platform-admin back office remains
- [x] Audit log table + `accept_offer` writes audit entries; extend to all
      state-changing actions
- [ ] i18n scaffolding (multi-language); multi-currency money handling is in
      place on RFQs/offers/orders

## Phase 1a — Construction Marketplace (MVP)

- [x] Company registration and standardized profile (profile fields, services,
      portfolio; logo/cover upload via media buckets)
- [x] Permanent SEO-friendly company URLs (`/company/<slug>`); structured data
      markup remains
- [x] Company search with country/category/rating/verified filters (region/city
      and language filters remain)
- [x] RFQ flow: customer posts description, images, address, budget, deadline,
      preferred language + vertical-specific metadata
- [ ] RFQ matching → notifications to matching companies (companies browse the
      open-request inbox today; push/email matching remains)
- [x] Offers: companies submit quotations; customer accepts → Order created
      (transactional `accept_offer`)
- [ ] Messaging UI between customer and company (schema + RLS are in place)
- [x] Order completion → verified customer review (all review dimensions)
- [ ] Verification v1 back office: identity + VAT approval workflow
      (request tables, levels and badges are in place)
- [x] Trust Score v1: verification, reviews, completed projects, response metrics
      — continuously recalculated by database triggers

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
