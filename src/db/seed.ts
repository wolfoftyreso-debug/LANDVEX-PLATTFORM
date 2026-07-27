/**
 * Seed: LT→SE corridor, welding/fitting trades, the ten-requirement
 * catalogue (Section 5/M1) and the first admin/ops users.
 * New corridors are seeds, not code.
 */
import { and, eq } from "drizzle-orm";
import { db, pool } from "@/lib/db";
import { logger } from "@/lib/logger";
import { corridors, requirementDefinitions, trades } from "@/modules/catalog/schema";
import { users } from "@/modules/identity/schema";
import { hashPassword } from "@/modules/identity/password";

async function main() {
  // Trades — data, not code (Section 2). Broadened per the 2026-07
  // repositioning: construction and property trades alongside the
  // original industrial launch trades.
  const TRADE_SEED = [
    { slug: "welding", nameEn: "Welding", nameSv: "Svetsning", nameLt: "Suvirinimas", nameLv: "Metināšana", nameEt: "Keevitus", namePl: "Spawanie" },
    { slug: "industrial-fitting", nameEn: "Industrial fitting", nameSv: "Industrimontage", nameLt: "Pramoninis montavimas", nameLv: "Rūpnieciskā montāža", nameEt: "Tööstuslik montaaž", namePl: "Montaż przemysłowy" },
    { slug: "carpentry", nameEn: "Carpentry", nameSv: "Snickeri", nameLt: "Staliaus darbai", nameLv: "Galdniecība", nameEt: "Puusepatööd", namePl: "Stolarka" },
    { slug: "painting", nameEn: "Painting", nameSv: "Målning", nameLt: "Dažymas", nameLv: "Krāsošana", nameEt: "Maalritööd", namePl: "Malowanie" },
    { slug: "tiling", nameEn: "Tiling", nameSv: "Plattsättning", nameLt: "Plytelių klojimas", nameLv: "Flīzēšana", nameEt: "Plaatimistööd", namePl: "Układanie płytek" },
    { slug: "roofing", nameEn: "Roofing", nameSv: "Tak", nameLt: "Stogų darbai", nameLv: "Jumta darbi", nameEt: "Katusetööd", namePl: "Prace dachowe" },
    { slug: "concrete", nameEn: "Concrete", nameSv: "Betong", nameLt: "Betonavimas", nameLv: "Betonēšana", nameEt: "Betoonitööd", namePl: "Prace betoniarskie" },
    { slug: "electrical", nameEn: "Electrical", nameSv: "El", nameLt: "Elektros darbai", nameLv: "Elektrības darbi", nameEt: "Elektritööd", namePl: "Prace elektryczne" },
    { slug: "plumbing-hvac", nameEn: "Plumbing & HVAC", nameSv: "VVS", nameLt: "Santechnika ir ŠVOK", nameLv: "Santehnika un AVK", nameEt: "Torutööd ja ventilatsioon", namePl: "Hydraulika i HVAC" },
    { slug: "groundworks", nameEn: "Groundworks", nameSv: "Markarbeten", nameLt: "Žemės darbai", nameLv: "Zemes darbi", nameEt: "Mullatööd", namePl: "Roboty ziemne" },
    { slug: "steel-structures", nameEn: "Steel structures", nameSv: "Stål", nameLt: "Plieno konstrukcijos", nameLv: "Tērauda konstrukcijas", nameEt: "Teraskonstruktsioonid", namePl: "Konstrukcje stalowe" },
    { slug: "demolition", nameEn: "Demolition", nameSv: "Rivning", nameLt: "Griovimo darbai", nameLv: "Nojaukšanas darbi", nameEt: "Lammutustööd", namePl: "Prace rozbiórkowe" },
    { slug: "property-services", nameEn: "Property services", nameSv: "Fastighetsservice", nameLt: "Pastatų priežiūra", nameLv: "Īpašumu apsaimniekošana", nameEt: "Kinnisvarahooldus", namePl: "Obsługa nieruchomości" },
  ];
  const [welding] = await db
    .insert(trades)
    .values(TRADE_SEED)
    .onConflictDoNothing()
    .returning();

  // Backfill lv/et/pl names on databases seeded before migration 0006
  for (const t of TRADE_SEED) {
    await db
      .update(trades)
      .set({ nameLv: t.nameLv, nameEt: t.nameEt, namePl: t.namePl })
      .where(eq(trades.slug, t.slug));
  }

  const weldingTrade =
    welding ??
    (await db.query.trades.findFirst({ where: eq(trades.slug, "welding") }));

  // Corridors — LT→SE (launch) and PL→SE. New corridors are seeds, not code.
  const ensureCorridor = async (slug: string, fromCountry: string) => {
    const [row] = await db
      .insert(corridors)
      .values({ slug, fromCountry, toCountry: "SE", serviceType: "entreprenad" })
      .onConflictDoNothing()
      .returning();
    const found =
      row ?? (await db.query.corridors.findFirst({ where: eq(corridors.slug, slug) }));
    if (!found) throw new Error(`Corridor seed failed: ${slug}`);
    return found;
  };
  const corridor = await ensureCorridor("lt-se", "LT");
  const corridorPl = await ensureCorridor("pl-se", "PL");

  // Requirement catalogue — ten requirements per corridor, stored as data
  const R = (
    corridorId: string,
    key: string,
    nameEn: string,
    nameSv: string,
    nameLt: string,
    names: { lv: string; et: string; pl: string },
    scope: "company" | "worker" | "assignment",
    critical: 0 | 1,
    sortOrder: number,
    metadataSpec: Record<string, unknown> = {},
    tradeId: string | null = null,
  ) => ({
    corridorId,
    tradeId,
    key,
    nameEn,
    nameSv,
    nameLt,
    nameLv: names.lv,
    nameEt: names.et,
    namePl: names.pl,
    scope,
    critical,
    sortOrder,
    metadataSpec,
  });

  const REQ_SEED = [
    R(corridor.id, "registry_extract", "Company registry extract (Registrų centras)", "Registerutdrag (Registrų centras)", "Registrų centro išrašas", { lv: "Uzņēmumu reģistra izraksts", et: "Äriregistri väljavõte", pl: "Odpis z rejestru przedsiębiorców" }, "company", 1, 1),
    R(corridor.id, "f_skatt", "Swedish F-skatt approval (Skatteverket)", "Godkänd för F-skatt (Skatteverket)", "Švedijos F-skatt patvirtinimas", { lv: "Zviedrijas F-skatt apstiprinājums (Skatteverket)", et: "Rootsi F-skatt kinnitus (Skatteverket)", pl: "Zatwierdzenie F-skatt (Skatteverket)" }, "company", 1, 2, { fields: ["approval_date"] }),
    R(corridor.id, "vat_status", "VAT registration status", "Momsregistrering", "PVM registracijos statusas", { lv: "PVN reģistrācijas statuss", et: "KMKR registreeringu staatus", pl: "Status rejestracji VAT" }, "company", 1, 3),
    R(corridor.id, "a1_certificate", "A1 certificate per posted worker (Sodra)", "A1-intyg per utstationerad arbetare (Sodra)", "A1 pažymėjimas kiekvienam komandiruotam darbuotojui (Sodra)", { lv: "A1 sertifikāts katram norīkotajam darbiniekam", et: "A1 tõend iga lähetatud töötaja kohta", pl: "Zaświadczenie A1 dla każdego pracownika delegowanego" }, "worker", 1, 4, { fields: ["valid_from", "valid_until"] }),
    R(corridor.id, "posted_worker_notification", "Posted-worker notification receipt (Arbetsmiljöverket)", "Utstationeringsanmälan (Arbetsmiljöverket)", "Komandiruoto darbuotojo pranešimo kvitas", { lv: "Norīkošanas paziņojuma apstiprinājums (Arbetsmiljöverket)", et: "Lähetatud töötaja teavituse kinnitus (Arbetsmiljöverket)", pl: "Potwierdzenie zgłoszenia delegowania (Arbetsmiljöverket)" }, "assignment", 1, 5),
    R(corridor.id, "id06", "ID06 status per worker", "ID06 per arbetare", "ID06 statusas kiekvienam darbuotojui", { lv: "ID06 statuss katram darbiniekam", et: "ID06 staatus iga töötaja kohta", pl: "Status ID06 dla każdego pracownika" }, "worker", 1, 6),
    R(corridor.id, "liability_insurance", "Liability insurance (ansvarsförsäkring)", "Ansvarsförsäkring", "Civilinės atsakomybės draudimas", { lv: "Civiltiesiskās atbildības apdrošināšana", et: "Vastutuskindlustus", pl: "Ubezpieczenie OC" }, "company", 1, 7, { fields: ["insurer", "coverage_amount_minor", "coverage_currency", "expiry"] }),
    R(corridor.id, "collective_agreement", "Collective-agreement status", "Kollektivavtalsstatus", "Kolektyvinės sutarties statusas", { lv: "Koplīguma statuss", et: "Kollektiivlepingu staatus", pl: "Status układu zbiorowego" }, "company", 0, 8, { enum: ["member", "hangavtal", "none"] }),
    R(corridor.id, "welder_qualifications", "Welder qualifications ISO 9606-1 per worker; EN 1090 EXC class", "Svetsarprövning ISO 9606-1 per arbetare; EN 1090 EXC-klass", "Suvirintojų kvalifikacija ISO 9606-1; EN 1090 EXC klasė", { lv: "Metinātāju kvalifikācija ISO 9606-1; EN 1090 EXC klase", et: "Keevitajate kvalifikatsioon ISO 9606-1; EN 1090 EXC klass", pl: "Kwalifikacje spawaczy ISO 9606-1; klasa EXC wg EN 1090" }, "worker", 1, 9, { fields: ["process", "valid_until", "en1090_exc_class"] }, weldingTrade?.id ?? null),
    R(corridor.id, "reference_projects", "Reference projects (minimum two, contactable)", "Referensprojekt (minst två, kontaktbara)", "Referenciniai projektai (bent du, su kontaktais)", { lv: "Atsauces projekti (vismaz divi, ar kontaktiem)", et: "Referentsprojektid (vähemalt kaks, kontaktidega)", pl: "Projekty referencyjne (min. dwa, z kontaktem)" }, "company", 0, 10, { min_count: 2 }),
  ];
  // PL→SE: same Swedish-side requirements, Polish home institutions
  // (registry: KRS/CEIDG instead of Registrų centras; A1 issuer: ZUS
  // instead of Sodra). Everything else is identical by design.
  const PL_REQ_SEED = [
    R(corridorPl.id, "registry_extract", "Company registry extract (KRS/CEIDG)", "Registerutdrag (KRS/CEIDG)", "Įmonių registro išrašas (KRS/CEIDG)", { lv: "Uzņēmumu reģistra izraksts (KRS/CEIDG)", et: "Äriregistri väljavõte (KRS/CEIDG)", pl: "Odpis z KRS lub wpis do CEIDG" }, "company", 1, 1),
    R(corridorPl.id, "f_skatt", "Swedish F-skatt approval (Skatteverket)", "Godkänd för F-skatt (Skatteverket)", "Švedijos F-skatt patvirtinimas", { lv: "Zviedrijas F-skatt apstiprinājums (Skatteverket)", et: "Rootsi F-skatt kinnitus (Skatteverket)", pl: "Zatwierdzenie F-skatt (Skatteverket)" }, "company", 1, 2, { fields: ["approval_date"] }),
    R(corridorPl.id, "vat_status", "VAT registration status", "Momsregistrering", "PVM registracijos statusas", { lv: "PVN reģistrācijas statuss", et: "KMKR registreeringu staatus", pl: "Status rejestracji VAT" }, "company", 1, 3),
    R(corridorPl.id, "a1_certificate", "A1 certificate per posted worker (ZUS)", "A1-intyg per utstationerad arbetare (ZUS)", "A1 pažymėjimas kiekvienam komandiruotam darbuotojui (ZUS)", { lv: "A1 sertifikāts katram norīkotajam darbiniekam (ZUS)", et: "A1 tõend iga lähetatud töötaja kohta (ZUS)", pl: "Zaświadczenie A1 dla każdego pracownika delegowanego (ZUS)" }, "worker", 1, 4, { fields: ["valid_from", "valid_until"] }),
    R(corridorPl.id, "posted_worker_notification", "Posted-worker notification receipt (Arbetsmiljöverket)", "Utstationeringsanmälan (Arbetsmiljöverket)", "Komandiruoto darbuotojo pranešimo kvitas", { lv: "Norīkošanas paziņojuma apstiprinājums (Arbetsmiljöverket)", et: "Lähetatud töötaja teavituse kinnitus (Arbetsmiljöverket)", pl: "Potwierdzenie zgłoszenia delegowania (Arbetsmiljöverket)" }, "assignment", 1, 5),
    R(corridorPl.id, "id06", "ID06 status per worker", "ID06 per arbetare", "ID06 statusas kiekvienam darbuotojui", { lv: "ID06 statuss katram darbiniekam", et: "ID06 staatus iga töötaja kohta", pl: "Status ID06 dla każdego pracownika" }, "worker", 1, 6),
    R(corridorPl.id, "liability_insurance", "Liability insurance (ansvarsförsäkring)", "Ansvarsförsäkring", "Civilinės atsakomybės draudimas", { lv: "Civiltiesiskās atbildības apdrošināšana", et: "Vastutuskindlustus", pl: "Ubezpieczenie OC" }, "company", 1, 7, { fields: ["insurer", "coverage_amount_minor", "coverage_currency", "expiry"] }),
    R(corridorPl.id, "collective_agreement", "Collective-agreement status", "Kollektivavtalsstatus", "Kolektyvinės sutarties statusas", { lv: "Koplīguma statuss", et: "Kollektiivlepingu staatus", pl: "Status układu zbiorowego" }, "company", 0, 8, { enum: ["member", "hangavtal", "none"] }),
    R(corridorPl.id, "welder_qualifications", "Welder qualifications ISO 9606-1 per worker; EN 1090 EXC class", "Svetsarprövning ISO 9606-1 per arbetare; EN 1090 EXC-klass", "Suvirintojų kvalifikacija ISO 9606-1; EN 1090 EXC klasė", { lv: "Metinātāju kvalifikācija ISO 9606-1; EN 1090 EXC klase", et: "Keevitajate kvalifikatsioon ISO 9606-1; EN 1090 EXC klass", pl: "Kwalifikacje spawaczy ISO 9606-1; klasa EXC wg EN 1090" }, "worker", 1, 9, { fields: ["process", "valid_until", "en1090_exc_class"] }, weldingTrade?.id ?? null),
    R(corridorPl.id, "reference_projects", "Reference projects (minimum two, contactable)", "Referensprojekt (minst två, kontaktbara)", "Referenciniai projektai (bent du, su kontaktais)", { lv: "Atsauces projekti (vismaz divi, ar kontaktiem)", et: "Referentsprojektid (vähemalt kaks, kontaktidega)", pl: "Projekty referencyjne (min. dwa, z kontaktem)" }, "company", 0, 10, { min_count: 2 }),
  ];

  const ALL_REQS = [...REQ_SEED, ...PL_REQ_SEED];
  await db.insert(requirementDefinitions).values(ALL_REQS).onConflictDoNothing();

  // Backfill lv/et/pl names on databases seeded before migration 0006
  for (const r of ALL_REQS) {
    await db
      .update(requirementDefinitions)
      .set({ nameLv: r.nameLv, nameEt: r.nameEt, namePl: r.namePl })
      .where(
        and(
          eq(requirementDefinitions.corridorId, r.corridorId),
          eq(requirementDefinitions.key, r.key),
        ),
      );
  }

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

  logger.info(
    "seed complete: corridors lt-se + pl-se, 13 trades, 10 requirements each, 2 users",
  );
  await pool.end();
}

main().catch((error) => {
  logger.error(error, "seed failed");
  process.exit(1);
});
