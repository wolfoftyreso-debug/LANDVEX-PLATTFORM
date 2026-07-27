/**
 * Initial Baltic Bridge catalog (30 profiles) — imported as UNCLAIMED.
 *
 * Data policy (per the catalog brief):
 * - Only facts published on open, public sources (B2B directories, EU
 *   partnering portals, the companies' own public pages). Source URL is
 *   stored on every profile and shown publicly for attribution.
 * - No personal contact data (GDPR): the public website is the contact path.
 * - No logos or images — none are licensed for reuse.
 * - Every profile is claimable: the company takes it over via the claim
 *   flow, reviewed by ops; verification (the badge) is a separate process
 *   and is NEVER granted by import.
 *
 * Descriptions paraphrase the sources; where a fact (city, founding year)
 * was not stated by the source it is left empty rather than guessed.
 */
import { eq } from "drizzle-orm";
import { db, pool } from "@/lib/db";
import { logger } from "@/lib/logger";
import { users } from "@/modules/identity/schema";
import { companies, companySlugs } from "@/modules/companies/schema";
import { slugify } from "@/modules/companies/service";
import { writeAudit, appendOutbox } from "@/modules/audit/service";

interface CatalogEntry {
  name: string;
  country: "LT" | "LV" | "EE" | "PL";
  city?: string;
  category: string;
  description: string;
  website?: string;
  yearFounded?: number;
  /** Only certifications/awards explicitly stated on the cited source page */
  certifications?: string[];
  awards?: string[];
  sourceUrl: string;
  sourceName: string;
}

/** Facts found later for companies already imported — applied as updates */
interface CatalogEnrichment {
  name: string;
  certifications?: string[];
  awards?: string[];
  city?: string;
  yearFounded?: number;
  website?: string;
  sourceUrl: string;
  sourceName: string;
}

const WELD = "Welding & metal fabrication";
const PIPE = "Industrial piping & installation";
const CNC = "CNC machining";
const MARINE = "Shipbuilding & marine";
const STEEL = "Steel structures";
const STAINLESS = "Stainless equipment";

const CATALOG: CatalogEntry[] = [
  // ------------------------------------------------------------ Lithuania
  { name: "Westa Steel UAB", country: "LT", category: PIPE,
    description: "Pipe welding, installation, reconstruction and repair of steel parts and equipment. Subcontractor to major Lithuanian and foreign petrochemical, food-industry, pharmaceutical, construction and shipping companies.",
    website: "https://www.westasteel.lt", sourceUrl: "https://www.westasteel.lt/en/about-us/", sourceName: "westasteel.lt (company site)" },
  { name: "Rokvelas UAB", country: "LT", category: WELD,
    description: "Metal working services for small-serial and serial production, with over a decade of export experience.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/steel-and-metal-fabrication.html", sourceName: "Europages" },
  { name: "Bermetix UAB", country: "LT", city: "Vilnius", category: STAINLESS,
    description: "European manufacturer of custom stainless steel tanks and process vessels.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/welding.html", sourceName: "Europages" },
  { name: "Lavango Engineering LT UAB", country: "LT", category: STAINLESS,
    description: "Manufactures stainless steel equipment for the food industry.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "Anvalda UAB", country: "LT", category: WELD,
    description: "Metal processing company with over 19 years of experience; services include TIG, MIG and MAG welding.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "KELLA Engineering", country: "LT", category: WELD,
    description: "Metal fabrication services specializing in outsourced fabrication work.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/welding%20work%20-%20steels%20and%20metal.html", sourceName: "Europages" },
  { name: "GRR Engineering UAB", country: "LT", category: WELD,
    description: "Manufactures industrial heat-treatment equipment and provides metal working services.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "Stansefabrikken Automotive UAB", country: "LT", yearFounded: 2008, category: WELD,
    description: "Established in Lithuania in 2008; specializes in stamping, automatic welding and Tier 2 automotive supply.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "Martema UAB", country: "LT", yearFounded: 2004, category: WELD,
    description: "Metal processing and construction manufacturing services in Lithuania and across Europe since 2004.",
    sourceUrl: "https://www.europages.co.uk/companies/lithuania/metalworking.html", sourceName: "Europages" },
  { name: "OSS UAB", country: "LT", category: PIPE,
    description: "Industrial piping installation and welding. Active in 15 countries over two decades, with representative offices in Sweden, Finland and Norway.",
    website: "https://www.oss.lt", sourceUrl: "https://www.oss.lt/", sourceName: "oss.lt (company site)" },
  { name: "Kijora UAB", country: "LT", yearFounded: 2014, category: PIPE,
    description: "Piping systems manufacturing and installation since 2014: welders, pipe fitters and plumbers executing plumbing, welding, pipeline installation and metal work to EU requirements.",
    website: "https://kijora.lt", sourceUrl: "https://kijora.lt/en/", sourceName: "kijora.lt (company site)" },
  { name: "Feliuga UAB", country: "LT", yearFounded: 2001, category: PIPE,
    description: "Prefabrication of pipe spools and piping components for power, petrochemical, paper-cellulose, offshore and shipbuilding projects since 2001.",
    sourceUrl: "https://www.copiermachinery.com/en/about-us/case-studies/feliuga-uab-increased-productivity-by-400/", sourceName: "Copier Machinery case study" },
  { name: "Western Baltija Shipbuilding UAB", country: "LT", city: "Klaipėda", category: MARINE,
    description: "Shipbuilding company with 70+ years of heritage and more than 600 employees, part of the Western Shipyard Group in Klaipėda.",
    website: "https://wbs.lt", sourceUrl: "https://wbs.lt/en/", sourceName: "wbs.lt (company site)" },
  { name: "Marine Technology (Western Shipyard Group)", country: "LT", city: "Klaipėda", category: MARINE,
    description: "Engineering, manufacturing and maintenance of complex structural steel components and cable-handling solutions for offshore energy, oil and gas; investing in robotic welding capacity at Klaipėda Seaport.",
    sourceUrl: "https://investlithuania.com/news/marine-technology-to-invest-e15m-in-advanced-manufacturing-expansion-in-klaipeda/", sourceName: "Invest Lithuania" },
  // -------------------------------------------------------------- Latvia
  { name: "Ritausmas Steel Constructions SIA", country: "LV", city: "Riga", yearFounded: 2013, category: STEEL,
    description: "Metal fabrication partner operating a 6 000 m² facility in Riga: laser and plasma cutting, sheet metal bending and certified steel structures to EN 3834 and EN 1090. Customers across Latvia and the Nordics.",
    website: "https://ritausmas.lv", sourceUrl: "https://ritausmas.lv/en/", sourceName: "ritausmas.lv (company site)" },
  { name: "Industrial Welding SIA", country: "LV", category: WELD,
    description: "Metal product manufacturer, part of a holding group with 25 years of experience.",
    sourceUrl: "https://www.emis.com/php/company-profile/LV/Industrial_Welding_SIA_en_9994966.html", sourceName: "EMIS company profile" },
  { name: "EMJ Metals SIA", country: "LV", category: WELD,
    description: "Metalworking, sheet metal processing and fabrication.",
    website: "https://www.emjmetals.lv", sourceUrl: "https://www.emjmetals.lv/", sourceName: "emjmetals.lv (company site)" },
  { name: "Metal Constructions (metals.lv)", country: "LV", category: STEEL,
    description: "Latvian manufacturer of metal constructions.",
    website: "https://metals.lv", sourceUrl: "https://metals.lv/en/", sourceName: "metals.lv (company site)" },
  { name: "CNC Latvia Ltd", country: "LV", city: "Riga", yearFounded: 2013, category: CNC,
    description: "Precision CNC turning and milling since 2013, exporting mainly to customers in Sweden, Norway and Finland.",
    website: "https://cnclatvia.com", sourceUrl: "https://cnclatvia.com/", sourceName: "cnclatvia.com (company site)" },
  { name: "Energoimpex Metal", country: "LV", city: "Ventspils", category: CNC,
    description: "Export-oriented CNC machining with 11 CNC machines, positioned near the Freeport of Ventspils.",
    sourceUrl: "https://metal.energoimpex.eu/cnc-machining/", sourceName: "energoimpex.eu (company site)" },
  { name: "Metalmeistars Ltd", country: "LV", yearFounded: 1998, category: WELD,
    description: "Latvian family business founded in 1998, providing precision metalworking in the Baltic states.",
    website: "https://www.metal.lv", sourceUrl: "https://www.metal.lv/en", sourceName: "metal.lv (company site)" },
  { name: "AB Metal Ltd", country: "LV", yearFounded: 2005, category: WELD,
    description: "Founded in 2005 within the Metalmeistars family of companies to develop export-market operations.",
    sourceUrl: "https://www.metal.lv/en", sourceName: "metal.lv (company site)" },
  // ------------------------------------------------------------- Estonia
  { name: "AGMA OÜ", country: "EE", city: "Tallinn", yearFounded: 2011, category: WELD,
    description: "Precision metal fabrication for demanding sectors: high-integrity metal structures for offshore, gas, oil, engineering and construction. 20–49 employees.",
    sourceUrl: "https://www.europages.co.uk/AGMA/00000003878045-298430001.html", sourceName: "Europages" },
  { name: "Monik OÜ", country: "EE", city: "Tallinn", category: STEEL,
    description: "Installation of metal structures in Estonia and Scandinavia; workshops equipped for welding, plasma cutting, forming and rolling in carbon, high-alloy and aluminium steels.",
    website: "https://www.monik.ee", sourceUrl: "https://www.monik.ee/", sourceName: "monik.ee (company site)" },
  { name: "Bernal Estonia OÜ", country: "EE", category: WELD,
    description: "Estonian metal fabrication company — \"let's create metal possibilities\".",
    website: "https://bernal.ee", sourceUrl: "https://bernal.ee/en/", sourceName: "bernal.ee (company site)" },
  { name: "Steel Element OÜ", country: "EE", city: "Tallinn", yearFounded: 2018, category: STEEL,
    description: "Steel fabrication with a capacity of 300 tonnes per month; installation services across Estonia, Scandinavia and Europe.",
    website: "https://steelelement.ee", sourceUrl: "https://steelelement.ee/en/", sourceName: "steelelement.ee (company site)" },
  { name: "Metalset OÜ", country: "EE", category: PIPE,
    description: "Prefabrication and installation of industrial pipelines and steel structures up to EXC3; approved supplier at several European companies.",
    website: "https://metalset.eu", sourceUrl: "https://metalset.eu/", sourceName: "metalset.eu (company site)" },
  { name: "Levstal Group", country: "EE", category: STEEL,
    description: "Metal engineering and steel fabrication, delivering structures to clients in Finland, Germany, Norway, Sweden, Austria, Italy and beyond.",
    website: "https://levstal.com", sourceUrl: "https://levstal.com/", sourceName: "levstal.com (company site)" },
  { name: "Scanweld AS", country: "EE", category: PIPE,
    description: "Fabrication and installation as core competences within industrial piping and steel work.",
    website: "https://www.scanweld.ee", sourceUrl: "https://www.scanweld.ee/core-competence/our-core-competence/fabrication-installation/", sourceName: "scanweld.ee (company site)" },
  { name: "Radius Machining OÜ", country: "EE", city: "Tallinn", category: CNC,
    description: "Serial CNC turning and milling for two decades, from mechanical engineering to aerospace, with sites in Tallinn, Tartu and Pärnu serving Scandinavian and Central European customers.",
    sourceUrl: "https://estonianexport.ee/directory/listing/radius-machining-ou/", sourceName: "Estonian Export Directory" },
];

/** Later-sourced public facts for already-imported profiles (see importer) */
const ENRICHMENTS: CatalogEnrichment[] = [];

async function main() {
  const admin = await db.query.users.findFirst({
    where: eq(users.email, "admin@balticbridge.example"),
  });
  if (!admin) throw new Error("Run npm run db:seed first");

  let created = 0;
  for (const entry of CATALOG) {
    const existing = await db.query.companies.findFirst({
      where: eq(companies.name, entry.name),
    });
    if (existing) continue;

    await db.transaction(async (tx) => {
      const [company] = await tx
        .insert(companies)
        .values({
          name: entry.name,
          country: entry.country,
          city: entry.city,
          description: entry.description,
          website: entry.website,
          yearFounded: entry.yearFounded,
          category: entry.category,
          claimStatus: "unclaimed",
          sourceUrl: entry.sourceUrl,
          sourceName: entry.sourceName,
          languages: [],
          certifications: entry.certifications ?? [],
          awards: entry.awards ?? [],
        })
        .returning();
      if (!company) throw new Error("insert failed");

      await tx.insert(companySlugs).values({
        companyId: company.id,
        slug: slugify(entry.name, entry.country),
      });
      await writeAudit(tx, {
        actorId: admin.id,
        entityType: "company",
        entityId: company.id,
        action: "company.imported_from_open_source",
        after: { sourceUrl: entry.sourceUrl, sourceName: entry.sourceName },
      });
      await appendOutbox(tx, "companies.imported", { companyId: company.id });
    });
    created += 1;
  }

  // Enrichment: apply later-sourced facts to already-imported profiles.
  // Only fills fields, never downgrades claim status or touches ownership.
  let enriched = 0;
  for (const patch of ENRICHMENTS) {
    const existing = await db.query.companies.findFirst({
      where: eq(companies.name, patch.name),
    });
    if (!existing) continue;

    const set: Record<string, unknown> = {};
    if (patch.certifications?.length) set.certifications = patch.certifications;
    if (patch.awards?.length) set.awards = patch.awards;
    if (patch.city && !existing.city) set.city = patch.city;
    if (patch.yearFounded && !existing.yearFounded) set.yearFounded = patch.yearFounded;
    if (patch.website && !existing.website) set.website = patch.website;
    if (Object.keys(set).length === 0) continue;

    await db.transaction(async (tx) => {
      await tx
        .update(companies)
        .set({ ...set, updatedAt: new Date() })
        .where(eq(companies.id, existing.id));
      await writeAudit(tx, {
        actorId: admin.id,
        entityType: "company",
        entityId: existing.id,
        action: "company.enriched_from_open_source",
        before: {
          certifications: existing.certifications,
          awards: existing.awards,
        },
        after: { ...set, sourceUrl: patch.sourceUrl, sourceName: patch.sourceName },
      });
    });
    enriched += 1;
  }

  logger.info(
    `catalog seed complete: ${created} new unclaimed profiles (${CATALOG.length} total in catalog), ${enriched} enriched`,
  );
  await pool.end();
}

main().catch((error) => {
  logger.error(error, "catalog seed failed");
  process.exit(1);
});
