import { and, asc, eq, isNull } from "drizzle-orm";
import { db } from "@/lib/db";
import { requireAnyRole, type Actor } from "@/modules/identity/rbac";
import { appendOutbox, writeAudit } from "@/modules/audit/service";
import {
  capacityListings,
  companies,
  companyReferences,
  companySlugs,
  contacts,
  portfolioItems,
  workers,
} from "./schema";

export type Company = typeof companies.$inferSelect;
export type Worker = typeof workers.$inferSelect;
export type Contact = typeof contacts.$inferSelect;

export function slugify(name: string, country: string): string {
  const base = name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 50);
  return `${base}-${country.toLowerCase()}`;
}

export async function createCompany(
  actor: Actor,
  input: {
    name: string;
    country: string;
    registrationNumber?: string;
    vatNumber?: string;
    city?: string;
    description?: string;
    yearFounded?: number;
    headcount?: number;
    languages?: string[];
  },
  requestId?: string,
): Promise<Company> {
  // Ops onboards suppliers concierge-style; suppliers may also self-register
  // their own company (one per supplier account).
  requireAnyRole(actor, ["ops", "admin", "supplier"]);

  const isSelfServe = actor.role === "supplier";
  if (isSelfServe) {
    const existing = await getCompanyByOwner(actor.userId);
    if (existing) {
      throw new Error("Your account already has a company profile");
    }
  }

  return db.transaction(async (tx) => {
    const [company] = await tx
      .insert(companies)
      .values({
        name: input.name,
        country: input.country,
        registrationNumber: input.registrationNumber,
        vatNumber: input.vatNumber,
        city: input.city,
        description: input.description,
        yearFounded: input.yearFounded,
        headcount: input.headcount,
        languages: input.languages ?? [],
        ownerUserId: isSelfServe ? actor.userId : null,
      })
      .returning();
    if (!company) throw new Error("Company insert failed");

    await tx.insert(companySlugs).values({
      companyId: company.id,
      slug: slugify(input.name, input.country),
    });

    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "company",
      entityId: company.id,
      action: "company.created",
      after: { ...input, selfServe: isSelfServe },
      requestId,
    });
    await appendOutbox(tx, "companies.created", {
      companyId: company.id,
      selfServe: isSelfServe,
    });
    return company;
  });
}

/** The company owned by a supplier account (Alibaba model: one per account) */
export async function getCompanyByOwner(
  userId: string,
): Promise<Company | undefined> {
  return db.query.companies.findFirst({
    where: and(eq(companies.ownerUserId, userId), isNull(companies.deletedAt)),
  });
}

export async function addContact(
  actor: Actor,
  input: {
    companyId: string;
    name: string;
    email?: string;
    phone?: string;
    roleTitle?: string;
  },
): Promise<Contact> {
  requireAnyRole(actor, ["ops", "admin", "supplier"]);
  if (actor.role === "supplier") {
    const owned = await getCompanyByOwner(actor.userId);
    if (owned?.id !== input.companyId) {
      throw new Error("Suppliers can only manage their own company");
    }
  }

  return db.transaction(async (tx) => {
    const [contact] = await tx.insert(contacts).values(input).returning();
    if (!contact) throw new Error("Contact insert failed");
    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "contact",
      entityId: contact.id,
      action: "contact.created",
      after: { companyId: input.companyId },
    });
    return contact;
  });
}

export async function listCompanies(): Promise<Company[]> {
  return db
    .select()
    .from(companies)
    .where(isNull(companies.deletedAt))
    .orderBy(asc(companies.name));
}

export async function getCompany(id: string): Promise<Company | undefined> {
  return db.query.companies.findFirst({
    where: and(eq(companies.id, id), isNull(companies.deletedAt)),
  });
}

export async function listWorkers(companyId: string): Promise<Worker[]> {
  return db
    .select()
    .from(workers)
    .where(and(eq(workers.companyId, companyId), isNull(workers.deletedAt)))
    .orderBy(asc(workers.name));
}

export async function addWorker(
  actor: Actor,
  input: { companyId: string; name: string; tradeRole?: string },
): Promise<Worker> {
  requireAnyRole(actor, ["ops", "admin", "supplier"]);
  if (actor.role === "supplier") {
    const owned = await getCompanyByOwner(actor.userId);
    if (owned?.id !== input.companyId) {
      throw new Error("Suppliers can only manage their own company");
    }
  }

  return db.transaction(async (tx) => {
    const [worker] = await tx.insert(workers).values(input).returning();
    if (!worker) throw new Error("Worker insert failed");
    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "worker",
      entityId: worker.id,
      action: "worker.created",
      after: { companyId: input.companyId, tradeRole: input.tradeRole },
    });
    return worker;
  });
}

/** Editable profile fields (Alibaba-style supplier profile) */
export async function updateCompanyProfile(
  actor: Actor,
  companyId: string,
  patch: {
    description?: string;
    city?: string;
    website?: string;
    yearFounded?: number | null;
    headcount?: number | null;
    languages?: string[];
    certifications?: string[];
    awards?: string[];
    serviceAreas?: string[];
  },
): Promise<Company> {
  requireAnyRole(actor, ["ops", "admin", "supplier"]);
  if (actor.role === "supplier") {
    const owned = await getCompanyByOwner(actor.userId);
    if (owned?.id !== companyId) {
      throw new Error("Suppliers can only manage their own company");
    }
  }

  return db.transaction(async (tx) => {
    const [before] = await tx
      .select()
      .from(companies)
      .where(eq(companies.id, companyId));
    if (!before) throw new Error("Company not found");

    const [updated] = await tx
      .update(companies)
      .set({ ...patch, updatedAt: new Date() })
      .where(eq(companies.id, companyId))
      .returning();
    if (!updated) throw new Error("Company update failed");

    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "company",
      entityId: companyId,
      action: "company.profile_updated",
      before: {
        description: before.description,
        city: before.city,
        website: before.website,
        yearFounded: before.yearFounded,
        headcount: before.headcount,
        languages: before.languages,
      },
      after: patch,
    });
    await appendOutbox(tx, "companies.profile_updated", { companyId });
    return updated;
  });
}

/** Resolve a public slug. Non-primary slugs report the primary for redirect. */
export async function resolveCompanySlug(slug: string): Promise<{
  company: Company;
  primarySlug: string;
  isPrimary: boolean;
} | null> {
  const slugRow = await db.query.companySlugs.findFirst({
    where: eq(companySlugs.slug, slug),
  });
  if (!slugRow) return null;

  const company = await getCompany(slugRow.companyId);
  if (!company) return null;

  if (slugRow.isPrimary === 1) {
    return { company, primarySlug: slug, isPrimary: true };
  }
  const primary = await db.query.companySlugs.findFirst({
    where: and(
      eq(companySlugs.companyId, company.id),
      eq(companySlugs.isPrimary, 1),
    ),
  });
  return {
    company,
    primarySlug: primary?.slug ?? slug,
    isPrimary: primary?.slug === slug,
  };
}

export async function getPrimarySlug(companyId: string): Promise<string | null> {
  const row = await db.query.companySlugs.findFirst({
    where: and(
      eq(companySlugs.companyId, companyId),
      eq(companySlugs.isPrimary, 1),
    ),
  });
  return row?.slug ?? null;
}

export async function listPrimarySlugs(): Promise<
  { slug: string; updatedAt: Date }[]
> {
  const rows = await db
    .select({
      slug: companySlugs.slug,
      updatedAt: companies.updatedAt,
    })
    .from(companySlugs)
    .innerJoin(companies, eq(companies.id, companySlugs.companyId))
    .where(and(eq(companySlugs.isPrimary, 1), isNull(companies.deletedAt)));
  return rows;
}

// ---------------------------------------------------------------------------
// Capacity listings (M2): "our team is available" — the supply side signal
// ---------------------------------------------------------------------------
export type CapacityListing = typeof capacityListings.$inferSelect;

export async function createCapacityListing(
  actor: Actor,
  input: {
    companyId: string;
    tradeId: string;
    headcount: number;
    certificationsSummary?: string;
    earliestStart?: Date | null;
    weeksAvailable?: number | null;
    baseLocation?: string;
    publish?: boolean;
  },
): Promise<CapacityListing> {
  requireAnyRole(actor, ["ops", "admin", "supplier"]);
  if (actor.role === "supplier") {
    const owned = await getCompanyByOwner(actor.userId);
    if (owned?.id !== input.companyId) {
      throw new Error("Suppliers can only manage their own company");
    }
  }

  return db.transaction(async (tx) => {
    const [listing] = await tx
      .insert(capacityListings)
      .values({
        companyId: input.companyId,
        tradeId: input.tradeId,
        headcount: input.headcount,
        certificationsSummary: input.certificationsSummary,
        earliestStart: input.earliestStart ?? null,
        weeksAvailable: input.weeksAvailable ?? null,
        baseLocation: input.baseLocation,
        status: input.publish ? "published" : "draft",
      })
      .returning();
    if (!listing) throw new Error("Capacity listing insert failed");

    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "capacity_listing",
      entityId: listing.id,
      action: "capacity.created",
      after: { companyId: input.companyId, status: listing.status },
    });
    await appendOutbox(tx, "capacity.listing_created", {
      listingId: listing.id,
      companyId: input.companyId,
    });
    return listing;
  });
}

export async function listCompanyCapacity(
  companyId: string,
  onlyPublished = true,
): Promise<CapacityListing[]> {
  const conditions = onlyPublished
    ? and(
        eq(capacityListings.companyId, companyId),
        eq(capacityListings.status, "published"),
      )
    : eq(capacityListings.companyId, companyId);
  return db
    .select()
    .from(capacityListings)
    .where(conditions)
    .orderBy(asc(capacityListings.createdAt));
}

export async function setCapacityStatus(
  actor: Actor,
  listingId: string,
  status: "published" | "archived",
): Promise<void> {
  requireAnyRole(actor, ["ops", "admin", "supplier"]);
  const listing = await db.query.capacityListings.findFirst({
    where: eq(capacityListings.id, listingId),
  });
  if (!listing) throw new Error("Listing not found");
  if (actor.role === "supplier") {
    const owned = await getCompanyByOwner(actor.userId);
    if (owned?.id !== listing.companyId) {
      throw new Error("Suppliers can only manage their own company");
    }
  }
  await db
    .update(capacityListings)
    .set({ status, updatedAt: new Date() })
    .where(eq(capacityListings.id, listingId));
}

// ---------------------------------------------------------------------------
// Portfolio (project images) — moderated: pending until ops approves
// ---------------------------------------------------------------------------
export type PortfolioItem = typeof portfolioItems.$inferSelect;

export async function addPortfolioItem(
  actor: Actor,
  input: {
    companyId: string;
    title: string;
    description?: string;
    objectKey: string;
    contentType: string;
  },
): Promise<PortfolioItem> {
  requireAnyRole(actor, ["supplier", "ops", "admin"]);
  if (actor.role === "supplier") {
    const owned = await getCompanyByOwner(actor.userId);
    if (owned?.id !== input.companyId) {
      throw new Error("Suppliers can only manage their own company");
    }
  }

  return db.transaction(async (tx) => {
    const [item] = await tx
      .insert(portfolioItems)
      .values({ ...input, uploadedBy: actor.userId })
      .returning();
    if (!item) throw new Error("Portfolio insert failed");

    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "portfolio_item",
      entityId: item.id,
      action: "portfolio.submitted",
      after: { companyId: input.companyId, title: input.title },
    });
    await appendOutbox(tx, "companies.portfolio_submitted", {
      itemId: item.id,
      companyId: input.companyId,
    });
    return item;
  });
}

export async function listPortfolio(
  companyId: string,
  opts: { onlyApproved?: boolean } = { onlyApproved: true },
): Promise<PortfolioItem[]> {
  const where = opts.onlyApproved
    ? and(
        eq(portfolioItems.companyId, companyId),
        eq(portfolioItems.status, "approved"),
      )
    : eq(portfolioItems.companyId, companyId);
  return db
    .select()
    .from(portfolioItems)
    .where(where)
    .orderBy(asc(portfolioItems.createdAt));
}

export async function listPendingPortfolio(): Promise<PortfolioItem[]> {
  return db
    .select()
    .from(portfolioItems)
    .where(eq(portfolioItems.status, "pending"))
    .orderBy(asc(portfolioItems.createdAt));
}

export async function moderatePortfolioItem(
  actor: Actor,
  itemId: string,
  decision: "approved" | "rejected",
  note?: string,
): Promise<void> {
  requireAnyRole(actor, ["ops", "admin"]);

  await db.transaction(async (tx) => {
    const [item] = await tx
      .select()
      .from(portfolioItems)
      .where(eq(portfolioItems.id, itemId))
      .for("update");
    if (!item) throw new Error("Portfolio item not found");
    if (item.status !== "pending") throw new Error("Item already moderated");

    await tx
      .update(portfolioItems)
      .set({
        status: decision,
        moderationNote: note ?? null,
        moderatedBy: actor.userId,
        updatedAt: new Date(),
      })
      .where(eq(portfolioItems.id, itemId));

    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "portfolio_item",
      entityId: itemId,
      action: `portfolio.${decision}`,
      before: { status: item.status },
      after: { status: decision, note },
    });
  });
}

// ---------------------------------------------------------------------------
// References — collected and checked by ops (never a self-serve review flow)
// ---------------------------------------------------------------------------
export type CompanyReference = typeof companyReferences.$inferSelect;

export async function addReference(
  actor: Actor,
  input: {
    companyId: string;
    projectTitle: string;
    clientName: string;
    country: string;
    year?: number;
    scopeSummary?: string;
  },
): Promise<CompanyReference> {
  requireAnyRole(actor, ["ops", "admin"]);

  return db.transaction(async (tx) => {
    const [reference] = await tx
      .insert(companyReferences)
      .values({ ...input, collectedBy: actor.userId })
      .returning();
    if (!reference) throw new Error("Reference insert failed");

    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "company_reference",
      entityId: reference.id,
      action: "reference.collected",
      after: { companyId: input.companyId, clientName: input.clientName },
    });
    return reference;
  });
}

export async function listReferences(
  companyId: string,
): Promise<CompanyReference[]> {
  return db
    .select()
    .from(companyReferences)
    .where(eq(companyReferences.companyId, companyId))
    .orderBy(asc(companyReferences.createdAt));
}

// ---------------------------------------------------------------------------
// Catalog claims: imported (unclaimed) profiles are taken over by the real
// company through ops-reviewed verification — never automatically.
// ---------------------------------------------------------------------------

/** A signed-in supplier without a company requests to take over an
 * unclaimed catalog profile. Ops reviews before ownership is assigned. */
export async function requestClaim(
  actor: Actor,
  companyId: string,
): Promise<void> {
  requireAnyRole(actor, ["supplier"]);
  const company = await getCompany(companyId);
  if (!company) throw new Error("Company not found");
  if (company.claimStatus !== "unclaimed") {
    throw new Error("This profile is not open for claims");
  }
  const owned = await getCompanyByOwner(actor.userId);
  if (owned) throw new Error("Your account already has a company profile");

  await db.transaction(async (tx) => {
    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "company",
      entityId: companyId,
      action: "company.claim_requested",
      after: { claimantUserId: actor.userId },
    });
    await appendOutbox(tx, "companies.claim_requested", {
      companyId,
      claimantUserId: actor.userId,
      companyName: company.name,
    });
  });
}

/** Ops approves a claim: assigns ownership and marks the profile claimed.
 * The verification case (badge) remains a separate, ops-driven process. */
export async function assignOwnership(
  actor: Actor,
  companyId: string,
  ownerEmail: string,
): Promise<void> {
  requireAnyRole(actor, ["ops", "admin"]);
  const { getUserByEmail } = await import("@/modules/identity/service");
  const owner = await getUserByEmail(ownerEmail);
  if (!owner) throw new Error("No account with that email");
  if (owner.role !== "supplier") {
    throw new Error("Ownership can only be assigned to a supplier account");
  }
  const alreadyOwned = await getCompanyByOwner(owner.id);
  if (alreadyOwned && alreadyOwned.id !== companyId) {
    throw new Error("That account already owns another company");
  }

  await db.transaction(async (tx) => {
    const [before] = await tx
      .select()
      .from(companies)
      .where(eq(companies.id, companyId));
    if (!before) throw new Error("Company not found");

    await tx
      .update(companies)
      .set({ ownerUserId: owner.id, claimStatus: "claimed", updatedAt: new Date() })
      .where(eq(companies.id, companyId));

    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "company",
      entityId: companyId,
      action: "company.claim_approved",
      before: { ownerUserId: before.ownerUserId, claimStatus: before.claimStatus },
      after: { ownerUserId: owner.id, claimStatus: "claimed" },
    });
    await appendOutbox(tx, "companies.claim_approved", {
      companyId,
      ownerUserId: owner.id,
    });
  });
}

export async function listContacts(companyId: string): Promise<Contact[]> {
  return db
    .select()
    .from(contacts)
    .where(and(eq(contacts.companyId, companyId), isNull(contacts.deletedAt)))
    .orderBy(asc(contacts.name));
}
