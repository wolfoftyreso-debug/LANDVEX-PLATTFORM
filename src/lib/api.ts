import { createHash } from "node:crypto";
import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import type { z } from "zod";
import { db } from "@/lib/db";
import { idempotencyKeys } from "@/modules/audit/schema";
import { currentActor } from "@/lib/auth";
import { ForbiddenError, type Actor } from "@/modules/identity/rbac";

export function apiError(status: number, message: string) {
  return NextResponse.json({ error: { message } }, { status });
}

export async function requireApiActor(): Promise<Actor> {
  const actor = await currentActor();
  if (!actor) throw new ForbiddenError("Not authenticated");
  return actor;
}

export function handleApiError(error: unknown) {
  if (error instanceof ForbiddenError) return apiError(403, error.message);
  if (error instanceof Error) return apiError(400, error.message);
  return apiError(500, "Internal error");
}

export function parseBody<S extends z.ZodTypeAny>(
  schema: S,
  body: unknown,
): z.output<S> {
  const result = schema.safeParse(body);
  if (!result.success) {
    throw new Error(
      `Validation failed: ${result.error.issues
        .map((i) => `${i.path.join(".")}: ${i.message}`)
        .join("; ")}`,
    );
  }
  return result.data;
}

/**
 * Idempotency keys on all record-creating POST endpoints (Section 4.5).
 * Same key + same payload -> replay stored response. Same key + different
 * payload -> 409.
 */
export async function withIdempotency(
  request: Request,
  body: unknown,
  handler: () => Promise<{ status: number; body: unknown }>,
): Promise<NextResponse> {
  const key = request.headers.get("idempotency-key");
  if (!key) {
    return apiError(400, "Idempotency-Key header is required");
  }

  const requestHash = createHash("sha256")
    .update(JSON.stringify(body ?? null))
    .digest("hex");

  const existing = await db.query.idempotencyKeys.findFirst({
    where: eq(idempotencyKeys.key, key),
  });
  if (existing) {
    if (existing.requestHash !== requestHash) {
      return apiError(409, "Idempotency key reused with a different payload");
    }
    return NextResponse.json(existing.responseBody, {
      status: Number(existing.statusCode ?? 200),
    });
  }

  const result = await handler();
  await db
    .insert(idempotencyKeys)
    .values({
      key,
      requestHash,
      responseBody: result.body,
      statusCode: String(result.status),
    })
    .onConflictDoNothing();

  return NextResponse.json(result.body, { status: result.status });
}
