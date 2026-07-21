# Baltic Bridge — Project Foundation

This repository is being developed into **Baltic Bridge**, a B2B and B2C marketplace
connecting customers with verified companies across Europe. The long-term vision is to
become the *Alibaba of European services*, starting with **construction** and
**automotive repair**.

> The current codebase originates from an earlier e-commerce project (Vite + React +
> shadcn/ui + Supabase). All new work must move the project toward the Baltic Bridge
> vision described here and in `docs/`.

## Non-negotiable platform qualities

Every architectural decision must preserve these properties. The platform is designed
from day one to be:

- **API First** — every capability is exposed through a documented API before any UI consumes it
- **Cloud Native** — containerized, stateless services, externalized configuration
- **Multi-tenant** — verticals (construction, automotive, …) share one platform core
- **Modular** — bounded modules with explicit contracts (see module map below)
- **Scalable** — must support millions of users without fundamental redesign
- **Self-hosted** — no hard dependency on a single proprietary PaaS
- **Production ready** — tests, observability, audit logging, GDPR compliance
- **Event driven** — modules communicate through domain events, not direct coupling

## Marketplace principle

Baltic Bridge **never performs the work**. It connects:

`Customers → Verified companies → Payment → Logistics → Reviews → Long-term trust`

## Core modules

Identity · Authentication · Users · Companies · Reviews · Messaging · RFQ · Offers ·
Orders · Payments · Logistics · Media · Notifications · Search · Trust Engine ·
Verification · Administration · Analytics · API Gateway

The **marketplace engine is generic**; each vertical defines its own categories,
metadata, workflows and filters. New verticals (manufacturing, legal, cleaning, …)
must be enable-able without changing the core. The **Logistics module is independent**
from the marketplace.

## Technical principles

Domain Driven Design (DDD) · Clean Architecture · CQRS where appropriate ·
Event-driven communication · REST + GraphQL · OpenAPI documentation · PostgreSQL ·
Redis · Object storage for media · OpenSearch/Elasticsearch full-text search ·
Docker + Kubernetes · CI/CD · Infrastructure as Code · RBAC · Audit logging ·
Multi-language · Multi-currency · GDPR · Monitoring and observability.

## Key documents

| Document | Purpose |
|---|---|
| `docs/VISION.md` | Product vision, marketplace principles, future verticals |
| `docs/ARCHITECTURE.md` | Module map, technical principles, event-driven design, deployment |
| `docs/DOMAIN-MODEL.md` | Entities: company profiles, trust score, reviews, RFQ/offers, verification levels |
| `docs/ROADMAP.md` | Phased plan from current codebase to Phase 1 marketplaces |

Read these before designing or implementing any feature. When a requirement conflicts
with the current codebase, the vision documents win.

## Working conventions

- TypeScript everywhere; strict typing at module boundaries
- Company pages are SEO-friendly with permanent URLs: `balticbridge.com/company/<slug>`
- Only verified customers may leave reviews
- Trust scores are calculated automatically and continuously updated (see Trust Engine in `docs/DOMAIN-MODEL.md`)
- Verification levels: Bronze → Silver → Gold → Platinum (harder to obtain, higher visibility)
- Run `npm run test` and `npm run lint` before committing
