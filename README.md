# Baltic Bridge

A B2B and B2C marketplace connecting customers with **verified companies** across
Europe — starting with construction and automotive repair. The long-term vision is
to become the Alibaba of European services.

Baltic Bridge never performs the work. It connects:

```
Customers → Verified companies → Payment → Logistics → Reviews → Long-term trust
```

## Documentation

| Document | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Project foundation and rules for AI-assisted development |
| [`docs/VISION.md`](docs/VISION.md) | Product vision, marketplace principles, future verticals |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Module map, event-driven design, technical principles |
| [`docs/DOMAIN-MODEL.md`](docs/DOMAIN-MODEL.md) | Bounded contexts, aggregates, trust score, RFQ/offer/order lifecycles |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phased plan from the current codebase to Phase 1 marketplaces |

## Platform qualities

API First · Cloud Native · Multi-tenant · Modular · Scalable · Self-hosted ·
Production ready · Event driven — designed to support millions of users without
fundamental redesign.

## Tech stack (current)

- Vite + React + TypeScript
- shadcn/ui + Tailwind CSS
- Supabase (PostgreSQL, auth, storage, edge functions) — Phase 1 infrastructure;
  all domain logic stays behind module boundaries so the platform remains
  self-hostable (see `docs/ARCHITECTURE.md`, "Migration note")

## Development

```sh
npm i          # install dependencies
npm run dev    # start dev server
npm run test   # run tests
npm run lint   # lint
npm run build  # production build
```

> Note: this repository originates from an earlier e-commerce project. Legacy pages
> and functions are being retired as part of Phase 0 — see `docs/ROADMAP.md`.
