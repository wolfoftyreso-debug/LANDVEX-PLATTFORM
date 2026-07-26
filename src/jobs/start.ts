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
    case "companies.created": {
      // Self-registered suppliers enter the concierge funnel: ops reviews
      // the profile and opens the verification case.
      if (payload.selfServe === true) {
        const { createOpsTask } = await import("@/modules/verification/service");
        await createOpsTask({
          title: "New self-registered supplier — review and open verification case",
          detail: `Company ${payload.companyId}`,
          companyId: String(payload.companyId),
          dueAt: new Date(),
        });
      }
      break;
    }
    case "identity.user_registered": {
      logger.info(payload, "user registered");
      break;
    }
    case "companies.portfolio_submitted": {
      const { createOpsTask } = await import("@/modules/verification/service");
      await createOpsTask({
        title: "Portfolio image awaiting moderation",
        detail: `Item ${payload.itemId}`,
        companyId: String(payload.companyId),
        dueAt: new Date(),
      });
      break;
    }
    case "companies.claim_requested": {
      const { createOpsTask } = await import("@/modules/verification/service");
      await createOpsTask({
        title: "Claim request — verify ownership and assign the profile",
        detail: `${payload.companyName} · claimant user ${payload.claimantUserId}`,
        companyId: String(payload.companyId),
        dueAt: new Date(),
      });
      break;
    }
    case "companies.claim_approved": {
      await notifyCompanyOwner(
        String(payload.companyId),
        "Your Baltic Bridge profile is now yours",
        "Ownership assigned. Sign in to your portal to complete verification and manage your profile: /portal",
      );
      break;
    }
    case "rfq.created": {
      const { createOpsTask } = await import("@/modules/verification/service");
      await createOpsTask({
        title: "New RFQ — qualify and select suppliers",
        detail: `RFQ ${payload.rfqId}`,
        dueAt: new Date(),
      });
      break;
    }
    case "rfq.dispatched_to_company": {
      await notifyCompanyOwner(
        String(payload.companyId),
        "New work request from Baltic Bridge",
        `A buyer request matching your profile was dispatched to you. Review and submit your offer: /portal/rfq/${payload.rfqId}`,
      );
      break;
    }
    case "offers.submitted": {
      await notifyRfqBuyer(
        String(payload.rfqId),
        "New offer on your request",
        `A verified supplier submitted an offer. Compare offers: /portal/rfq/${payload.rfqId}`,
      );
      break;
    }
    case "offers.accepted": {
      await notifyCompanyOwner(
        String(payload.companyId),
        "Your offer was accepted 🎉",
        `The buyer accepted your offer on RFQ /portal/rfq/${payload.rfqId}. Baltic Bridge ops will contact you about the work package.`,
      );
      const { createOpsTask } = await import("@/modules/verification/service");
      await createOpsTask({
        title: "Offer accepted — record the deal for invoicing",
        detail: `Offer ${payload.offerId} on RFQ ${payload.rfqId}`,
        companyId: String(payload.companyId),
        dueAt: new Date(),
      });
      break;
    }
    case "messaging.message_sent": {
      // Deep-linked email to the counterpart (Section 5/M3)
      const rfqId = String(payload.rfqId);
      const senderUserId = String(payload.senderUserId);
      const { getRfq } = await import("@/modules/rfq/service");
      const rfq = await getRfq(rfqId);
      if (rfq && rfq.buyerUserId !== senderUserId) {
        await notifyRfqBuyer(
          rfqId,
          "New message on your request",
          `Open the conversation: /portal/rfq/${rfqId}`,
        );
      } else {
        await notifyCompanyOwner(
          String(payload.companyId),
          "New message from the buyer",
          `Open the conversation: /portal/rfq/${rfqId}`,
        );
      }
      break;
    }
    default:
      logger.debug({ eventType }, "outbox event without subscriber");
  }
}

async function notifyCompanyOwner(
  companyId: string,
  subject: string,
  text: string,
): Promise<void> {
  const { getCompany } = await import("@/modules/companies/service");
  const { getUserById } = await import("@/modules/identity/service");
  const company = await getCompany(companyId);
  const owner = company?.ownerUserId
    ? await getUserById(company.ownerUserId)
    : null;
  if (!owner) {
    logger.info({ companyId, subject }, "no owner user to notify");
    return;
  }
  await emailProvider().send({ to: owner.email, subject, text });
}

async function notifyRfqBuyer(
  rfqId: string,
  subject: string,
  text: string,
): Promise<void> {
  const { getRfq } = await import("@/modules/rfq/service");
  const { getUserById } = await import("@/modules/identity/service");
  const rfq = await getRfq(rfqId);
  const buyer = rfq ? await getUserById(rfq.buyerUserId) : null;
  if (!buyer) return;
  await emailProvider().send({ to: buyer.email, subject, text });
}
