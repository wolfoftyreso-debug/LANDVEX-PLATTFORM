import { and, asc, eq, isNull } from "drizzle-orm";
import { db } from "@/lib/db";
import { requireAnyRole, type Actor } from "@/modules/identity/rbac";
import { appendOutbox, writeAudit } from "@/modules/audit/service";
import { companies, companySlugs, contacts, workers } from "./schema";

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

export async function listContacts(companyId: string): Promise<Contact[]> {
  return db
    .select()
    .from(contacts)
    .where(and(eq(contacts.companyId, companyId), isNull(contacts.deletedAt)))
    .orderBy(asc(contacts.name));
}
