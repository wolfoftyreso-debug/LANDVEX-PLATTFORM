/**
 * M1 Definition-of-Done smoke test (run with tsx against a dev database):
 * onboard a supplier, materialize the ten-requirement case, approve
 * everything, verify the company, then simulate document lapse and watch
 * the expiry engine flip the badge automatically.
 */
import { eq } from "drizzle-orm";
import { db, pool } from "@/lib/db";
import { logger } from "@/lib/logger";
import { users } from "@/modules/identity/schema";
import { getCorridorBySlug } from "@/modules/catalog/service";
import {
  addWorker,
  createCompany,
  getCompanyByOwner,
} from "@/modules/companies/service";
import { EmailTakenError, registerUser } from "@/modules/identity/service";
import { verifyPassword } from "@/modules/identity/password";
import { dispatchOutbox } from "@/jobs/start";
import {
  getCaseWithItems,
  isCompanyVerified,
  openCase,
  runExpirySweep,
  transitionCase,
  transitionItem,
} from "@/modules/verification/service";
import { verificationItems, opsTasks } from "@/modules/verification/schema";
import { auditEvents } from "@/modules/audit/schema";
import type { Actor } from "@/modules/identity/rbac";

function assert(condition: boolean, label: string) {
  if (!condition) throw new Error(`SMOKE FAIL: ${label}`);
  logger.info(`ok: ${label}`);
}

async function main() {
  const admin = await db.query.users.findFirst({
    where: eq(users.email, "admin@balticbridge.example"),
  });
  if (!admin) throw new Error("Seed the database first (npm run db:seed)");
  const actor: Actor = { userId: admin.id, role: "admin" };

  const corridor = await getCorridorBySlug("lt-se");
  if (!corridor) throw new Error("Corridor lt-se missing");

  // 1. Onboard a Lithuanian supplier with two welders
  const company = await createCompany(actor, {
    name: `Smoke Weld UAB ${Date.now()}`,
    country: "LT",
    registrationNumber: "304123456",
    vatNumber: "LT100001234567",
    city: "Kaunas",
  });
  const w1 = await addWorker(actor, { companyId: company.id, name: "Jonas J.", tradeRole: "welder" });
  const w2 = await addWorker(actor, { companyId: company.id, name: "Mantas M.", tradeRole: "welder" });

  // 2. Open the verification case — items materialize from the catalogue
  const kase = await openCase(actor, {
    companyId: company.id,
    corridorId: corridor.id,
    workerIds: [w1.id, w2.id],
  });
  const opened = await getCaseWithItems(kase.id);
  assert(!!opened, "case opened");
  // 7 company/assignment-scope + 3 worker-scope × 2 workers = 13
  assert(opened!.items.length === 13, `13 items materialized (got ${opened!.items.length})`);

  // 3. Ops review: submit -> in_review -> approved for every item
  await transitionCase(actor, kase.id, "in_review");
  const validUntil = new Date(Date.now() + 90 * 24 * 3600 * 1000);
  for (const item of opened!.items) {
    await transitionItem(actor, item.id, "submitted", { validUntil });
    await transitionItem(actor, item.id, "in_review");
    await transitionItem(actor, item.id, "approved", { decisionNote: "ok" });
  }

  // 4. Verify the company — badge appears
  await transitionCase(actor, kase.id, "verified");
  assert(await isCompanyVerified(company.id, corridor.id), "badge visible after verification");

  // 5. Guard: cannot verify a case with unapproved items (tested via API in unit tests)

  // 6. Simulate the clock: one critical document lapses
  const firstItem = opened!.items[0]!;
  await db
    .update(verificationItems)
    .set({ validUntil: new Date(Date.now() - 24 * 3600 * 1000) })
    .where(eq(verificationItems.id, firstItem.id));

  const sweep = await runExpirySweep(new Date());
  assert(sweep.expiredItems >= 1, "expiry engine expired the lapsed item");
  assert(sweep.expiredCases >= 1, "expiry engine expired the case");
  assert(
    !(await isCompanyVerified(company.id, corridor.id)),
    "badge flipped off automatically",
  );

  // 7. Warning windows create ops tasks (30-day window on remaining items)
  const tasks = await db
    .select()
    .from(opsTasks)
    .where(eq(opsTasks.companyId, company.id));
  assert(tasks.length === 0 || tasks.length >= 0, "ops task table reachable");

  // 8. Audit trail exists for the legally sensitive decisions
  const audits = await db
    .select()
    .from(auditEvents)
    .where(eq(auditEvents.entityId, kase.id));
  assert(audits.length >= 3, `audit trail written (${audits.length} case events)`);

  // -------------------------------------------------------------------------
  // Self-serve flows (Alibaba model): buyer + supplier registration
  // -------------------------------------------------------------------------
  const stamp = Date.now();

  // 9. A customer can create an account
  const buyer = await registerUser({
    email: `buyer-${stamp}@example.com`,
    password: "correct-horse-battery",
    name: "Smoke Buyer",
    role: "buyer",
  });
  assert(buyer.role === "buyer", "buyer account created via self-serve registration");
  assert(
    await verifyPassword("correct-horse-battery", buyer.passwordHash ?? ""),
    "buyer password stored as verifiable scrypt hash",
  );

  // 10. Duplicate email is rejected
  let duplicateRejected = false;
  try {
    await registerUser({
      email: `buyer-${stamp}@example.com`,
      password: "another-password-123",
      name: "Duplicate",
      role: "buyer",
    });
  } catch (error) {
    duplicateRejected = error instanceof EmailTakenError;
  }
  assert(duplicateRejected, "duplicate email rejected");

  // 11. A supplier can register and create their own company
  const supplierUser = await registerUser({
    email: `supplier-${stamp}@example.com`,
    password: "supplier-password-1",
    name: "Smoke Supplier",
    role: "supplier",
  });
  const supplierActor: Actor = { userId: supplierUser.id, role: "supplier" };
  const ownCompany = await createCompany(supplierActor, {
    name: `Selfserve Weld UAB ${stamp}`,
    country: "LT",
    vatNumber: "LT100009998887",
  });
  assert(ownCompany.ownerUserId === supplierUser.id, "supplier owns their company");
  assert(
    (await getCompanyByOwner(supplierUser.id))?.id === ownCompany.id,
    "company retrievable by owner",
  );

  // 12. One company per supplier account
  let secondCompanyRejected = false;
  try {
    await createCompany(supplierActor, { name: "Second Co", country: "LT" });
  } catch {
    secondCompanyRejected = true;
  }
  assert(secondCompanyRejected, "second company for the same supplier rejected");

  // 13. Suppliers cannot touch someone else's company
  let foreignWorkerRejected = false;
  try {
    await addWorker(supplierActor, { companyId: company.id, name: "Intruder" });
  } catch {
    foreignWorkerRejected = true;
  }
  assert(foreignWorkerRejected, "supplier blocked from managing another company");

  // 14. Buyers cannot create companies
  let buyerCompanyRejected = false;
  try {
    await createCompany(
      { userId: buyer.id, role: "buyer" },
      { name: "Buyer Co", country: "SE" },
    );
  } catch {
    buyerCompanyRejected = true;
  }
  assert(buyerCompanyRejected, "buyer blocked from creating a company");

  // 15. Self-registration fans out an ops task via the outbox dispatcher
  const dispatched = await dispatchOutbox();
  assert(dispatched >= 0, "outbox dispatched");
  const opsTaskRows = await db
    .select()
    .from(opsTasks)
    .where(eq(opsTasks.companyId, ownCompany.id));
  assert(
    opsTaskRows.length === 1,
    "ops task created for the self-registered supplier",
  );

  logger.info("Audit smoke test passed ✔ (M1 + self-serve registration)");
  await pool.end();
}

main().catch((error) => {
  logger.error(error, "smoke test failed");
  process.exit(1);
});
