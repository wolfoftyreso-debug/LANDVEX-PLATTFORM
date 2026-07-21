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
  requireAnyRole(actor, ["ops", "admin"]);

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
      after: input,
      requestId,
    });
    await appendOutbox(tx, "companies.created", { companyId: company.id });
    return company;
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
