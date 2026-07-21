/**
 * Seed: LT→SE corridor, welding/fitting trades, the ten-requirement
 * catalogue (Section 5/M1) and the first admin/ops users.
 * New corridors are seeds, not code.
 */
import { eq } from "drizzle-orm";
import { db, pool } from "@/lib/db";
import { logger } from "@/lib/logger";
import { corridors, requirementDefinitions, trades } from "@/modules/catalog/schema";
import { users } from "@/modules/identity/schema";
import { hashPassword } from "@/modules/identity/password";

async function main() {
  // Trades
  const [welding] = await db
    .insert(trades)
    .values([
      { slug: "welding", nameEn: "Welding", nameSv: "Svetsning", nameLt: "Suvirinimas" },
      { slug: "industrial-fitting", nameEn: "Industrial fitting", nameSv: "Industrimontage", nameLt: "Pramoninis montavimas" },
    ])
    .onConflictDoNothing()
    .returning();

  const weldingTrade =
    welding ??
    (await db.query.trades.findFirst({ where: eq(trades.slug, "welding") }));

  // Corridor LT -> SE
  const [corridorRow] = await db
    .insert(corridors)
    .values({ slug: "lt-se", fromCountry: "LT", toCountry: "SE", serviceType: "entreprenad" })
    .onConflictDoNothing()
    .returning();
  const corridor =
    corridorRow ??
    (await db.query.corridors.findFirst({ where: eq(corridors.slug, "lt-se") }));
  if (!corridor) throw new Error("Corridor seed failed");

  // Requirement catalogue — ten requirements, stored as data
  const R = (
    key: string,
    nameEn: string,
    nameSv: string,
    nameLt: string,
    scope: "company" | "worker" | "assignment",
    critical: 0 | 1,
    sortOrder: number,
    metadataSpec: Record<string, unknown> = {},
    tradeId: string | null = null,
  ) => ({
    corridorId: corridor.id,
    tradeId,
    key,
    nameEn,
    nameSv,
    nameLt,
    scope,
    critical,
    sortOrder,
    metadataSpec,
  });

  await db
    .insert(requirementDefinitions)
    .values([
      R("registry_extract", "Company registry extract (Registrų centras)", "Registerutdrag (Registrų centras)", "Registrų centro išrašas", "company", 1, 1),
      R("f_skatt", "Swedish F-skatt approval (Skatteverket)", "Godkänd för F-skatt (Skatteverket)", "Švedijos F-skatt patvirtinimas", "company", 1, 2, { fields: ["approval_date"] }),
      R("vat_status", "VAT registration status", "Momsregistrering", "PVM registracijos statusas", "company", 1, 3),
      R("a1_certificate", "A1 certificate per posted worker (Sodra)", "A1-intyg per utstationerad arbetare (Sodra)", "A1 pažymėjimas kiekvienam komandiruotam darbuotojui (Sodra)", "worker", 1, 4, { fields: ["valid_from", "valid_until"] }),
      R("posted_worker_notification", "Posted-worker notification receipt (Arbetsmiljöverket)", "Utstationeringsanmälan (Arbetsmiljöverket)", "Komandiruoto darbuotojo pranešimo kvitas", "assignment", 1, 5),
      R("id06", "ID06 status per worker", "ID06 per arbetare", "ID06 statusas kiekvienam darbuotojui", "worker", 1, 6),
      R("liability_insurance", "Liability insurance (ansvarsförsäkring)", "Ansvarsförsäkring", "Civilinės atsakomybės draudimas", "company", 1, 7, { fields: ["insurer", "coverage_amount_minor", "coverage_currency", "expiry"] }),
      R("collective_agreement", "Collective-agreement status", "Kollektivavtalsstatus", "Kolektyvinės sutarties statusas", "company", 0, 8, { enum: ["member", "hangavtal", "none"] }),
      R("welder_qualifications", "Welder qualifications ISO 9606-1 per worker; EN 1090 EXC class", "Svetsarprövning ISO 9606-1 per arbetare; EN 1090 EXC-klass", "Suvirintojų kvalifikacija ISO 9606-1; EN 1090 EXC klasė", "worker", 1, 9, { fields: ["process", "valid_until", "en1090_exc_class"] }, weldingTrade?.id ?? null),
      R("reference_projects", "Reference projects (minimum two, contactable)", "Referensprojekt (minst två, kontaktbara)", "Referenciniai projektai (bent du, su kontaktais)", "company", 0, 10, { min_count: 2 }),
    ])
    .onConflictDoNothing();

  // First internal users (concierge ops team). Change passwords immediately.
  const seedUsers: {
    email: string;
    name: string;
    role: "admin" | "ops";
  }[] = [
    { email: "admin@balticbridge.example", name: "Admin", role: "admin" },
    { email: "ops@balticbridge.example", name: "Ops", role: "ops" },
  ];
  for (const u of seedUsers) {
    await db
      .insert(users)
      .values({
        email: u.email,
        name: u.name,
        role: u.role,
        passwordHash: await hashPassword("change-me-now"),
        emailVerifiedAt: new Date(),
      })
      .onConflictDoNothing();
  }

  logger.info("seed complete: corridor lt-se, 2 trades, 10 requirements, 2 users");
  await pool.end();
}

main().catch((error) => {
  logger.error(error, "seed failed");
  process.exit(1);
});
