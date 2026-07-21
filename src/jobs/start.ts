import PgBoss from "pg-boss";
import { asc, eq, isNull } from "drizzle-orm";
import { db } from "@/lib/db";
import { env } from "@/lib/env";
import { logger } from "@/lib/logger";
import { outboxEvents } from "@/modules/audit/schema";
import { runExpirySweep } from "@/modules/verification/service";
import { emailProvider } from "@/modules/notifications/email";

const EXPIRY_JOB = "verification-expiry-sweep";
const OUTBOX_JOB = "outbox-dispatch";

/**
 * In-process job runner (Section 3: pg-boss inside the app container).
 * - nightly expiry sweep (30/14/3-day warnings, auto-expiry)
 * - outbox dispatcher fanning domain events out to subscribers
 */
export async function startJobs(): Promise<PgBoss> {
  const boss = new PgBoss(env.DATABASE_URL);
  boss.on("error", (error) => logger.error(error, "pg-boss error"));
  await boss.start();

  await boss.createQueue(EXPIRY_JOB);
  await boss.createQueue(OUTBOX_JOB);

  // Nightly at 02:00 UTC
  await boss.schedule(EXPIRY_JOB, "0 2 * * *");
  // Outbox dispatch every minute
  await boss.schedule(OUTBOX_JOB, "* * * * *");

  await boss.work(EXPIRY_JOB, async () => {
    const result = await runExpirySweep(new Date());
    logger.info(result, "expiry sweep finished");
  });

  await boss.work(OUTBOX_JOB, async () => {
    await dispatchOutbox();
  });

  logger.info("pg-boss started: expiry sweep + outbox dispatcher");
  return boss;
}

/** Fan unprocessed outbox events out to in-process subscribers */
export async function dispatchOutbox(): Promise<number> {
  const pending = await db
    .select()
    .from(outboxEvents)
    .where(isNull(outboxEvents.processedAt))
    .orderBy(asc(outboxEvents.occurredAt))
    .limit(100);

  for (const event of pending) {
    try {
      await handleEvent(event.eventType, event.payload as Record<string, unknown>);
    } catch (error) {
      logger.error({ error, eventId: event.id }, "outbox handler failed");
      continue; // leave unprocessed; retried next run
    }
    await db
      .update(outboxEvents)
      .set({ processedAt: new Date() })
      .where(eq(outboxEvents.id, event.id));
  }
  return pending.length;
}

async function handleEvent(
  eventType: string,
  payload: Record<string, unknown>,
): Promise<void> {
  switch (eventType) {
    case "verification.item_expiry_warning": {
      // Supplier email + ops visibility (ops task already created in-tx)
      await emailProvider().send({
        to: "ops@balticbridge.example",
        subject: `Document expiring in ${payload.daysUntilExpiry} days`,
        text: `Verification item ${payload.itemId} for company ${payload.companyId} expires soon (window: ${payload.window} days).`,
      });
      break;
    }
    case "verification.case_state_changed": {
      logger.info(payload, "case state changed");
      break;
    }
    default:
      logger.debug({ eventType }, "outbox event without subscriber");
  }
}
