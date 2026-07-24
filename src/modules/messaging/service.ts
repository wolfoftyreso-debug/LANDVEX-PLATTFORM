import { and, asc, desc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import type { Actor } from "@/modules/identity/rbac";
import { appendOutbox, writeAudit } from "@/modules/audit/service";
import { getCompanyByOwner } from "@/modules/companies/service";
import { getRfq } from "@/modules/rfq/service";
import { messageThreads, threadMessages } from "./schema";

export type MessageThread = typeof messageThreads.$inferSelect;
export type ThreadMessage = typeof threadMessages.$inferSelect;

/** Access: the RFQ's buyer, the thread company's owner, or ops/admin */
async function assertThreadAccess(
  actor: Actor,
  rfqId: string,
  companyId: string,
): Promise<void> {
  if (actor.role === "ops" || actor.role === "admin") return;
  if (actor.role === "buyer") {
    const rfq = await getRfq(rfqId);
    if (rfq?.buyerUserId === actor.userId) return;
  }
  if (actor.role === "supplier") {
    const company = await getCompanyByOwner(actor.userId);
    if (company?.id === companyId) return;
  }
  throw new Error("No access to this conversation");
}

/** One thread per RFQ–supplier pair (Section 5/M3) */
export async function getOrCreateThread(
  actor: Actor,
  rfqId: string,
  companyId: string,
): Promise<MessageThread> {
  await assertThreadAccess(actor, rfqId, companyId);

  const existing = await db.query.messageThreads.findFirst({
    where: and(
      eq(messageThreads.rfqId, rfqId),
      eq(messageThreads.companyId, companyId),
    ),
  });
  if (existing) return existing;

  const [thread] = await db
    .insert(messageThreads)
    .values({ rfqId, companyId })
    .returning();
  if (!thread) throw new Error("Thread creation failed");
  return thread;
}

export async function listMessages(
  actor: Actor,
  threadId: string,
): Promise<ThreadMessage[]> {
  const thread = await db.query.messageThreads.findFirst({
    where: eq(messageThreads.id, threadId),
  });
  if (!thread) throw new Error("Thread not found");
  await assertThreadAccess(actor, thread.rfqId, thread.companyId);

  return db
    .select()
    .from(threadMessages)
    .where(eq(threadMessages.threadId, threadId))
    .orderBy(asc(threadMessages.createdAt));
}

export async function sendMessage(
  actor: Actor,
  threadId: string,
  body: string,
): Promise<ThreadMessage> {
  const trimmed = body.trim();
  if (!trimmed) throw new Error("Empty message");
  if (trimmed.length > 4000) throw new Error("Message too long");

  const thread = await db.query.messageThreads.findFirst({
    where: eq(messageThreads.id, threadId),
  });
  if (!thread) throw new Error("Thread not found");
  await assertThreadAccess(actor, thread.rfqId, thread.companyId);

  return db.transaction(async (tx) => {
    const [message] = await tx
      .insert(threadMessages)
      .values({ threadId, senderUserId: actor.userId, body: trimmed })
      .returning();
    if (!message) throw new Error("Message insert failed");

    await writeAudit(tx, {
      actorId: actor.userId,
      entityType: "thread_message",
      entityId: message.id,
      action: "message.sent",
      after: { threadId },
    });
    // Email notification with deep link handled by the outbox dispatcher
    await appendOutbox(tx, "messaging.message_sent", {
      threadId,
      messageId: message.id,
      rfqId: thread.rfqId,
      companyId: thread.companyId,
      senderUserId: actor.userId,
    });
    return message;
  });
}

export async function listThreadsForRfq(
  actor: Actor,
  rfqId: string,
): Promise<MessageThread[]> {
  const rfq = await getRfq(rfqId);
  if (!rfq) return [];
  if (
    actor.role !== "ops" &&
    actor.role !== "admin" &&
    !(actor.role === "buyer" && rfq.buyerUserId === actor.userId)
  ) {
    // Suppliers only see their own pair thread
    const company = await getCompanyByOwner(actor.userId);
    if (!company) return [];
    const thread = await db.query.messageThreads.findFirst({
      where: and(
        eq(messageThreads.rfqId, rfqId),
        eq(messageThreads.companyId, company.id),
      ),
    });
    return thread ? [thread] : [];
  }
  return db
    .select()
    .from(messageThreads)
    .where(eq(messageThreads.rfqId, rfqId))
    .orderBy(desc(messageThreads.createdAt));
}
