import { auditEvents, outboxEvents } from "./schema";
import type { Tx } from "@/lib/db";

export interface AuditEntry {
  actorId: string | null;
  entityType: string;
  entityId?: string | null;
  action: string;
  before?: unknown;
  after?: unknown;
  requestId?: string | null;
}

/**
 * Write an audit event inside the caller's transaction.
 * Never weaken or bypass these writes (Section 8.5).
 */
export async function writeAudit(tx: Tx, entry: AuditEntry): Promise<void> {
  await tx.insert(auditEvents).values({
    actorId: entry.actorId,
    entityType: entry.entityType,
    entityId: entry.entityId ?? null,
    action: entry.action,
    before: entry.before ?? null,
    after: entry.after ?? null,
    requestId: entry.requestId ?? null,
  });
}

/** Append a domain event to the outbox in the same transaction (Section 4.3) */
export async function appendOutbox(
  tx: Tx,
  eventType: string,
  payload: Record<string, unknown>,
): Promise<void> {
  await tx.insert(outboxEvents).values({ eventType, payload });
}
