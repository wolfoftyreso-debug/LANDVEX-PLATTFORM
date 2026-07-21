import { NextResponse } from "next/server";
import { z } from "zod";
import { handleApiError, parseBody, requireApiActor } from "@/lib/api";
import { transitionItem } from "@/modules/verification/service";

export const dynamic = "force-dynamic";

const transitionSchema = z.object({
  status: z.enum([
    "missing",
    "submitted",
    "in_review",
    "approved",
    "rejected",
    "expired",
  ]),
  decisionNote: z.string().optional(),
  metadata: z.record(z.unknown()).optional(),
  validFrom: z.coerce.date().nullable().optional(),
  validUntil: z.coerce.date().nullable().optional(),
  documentIds: z.array(z.string().uuid()).optional(),
});

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const actor = await requireApiActor();
    const { id } = await params;
    const input = parseBody(transitionSchema, await request.json());
    const updated = await transitionItem(actor, id, input.status, input);
    return NextResponse.json({ data: updated });
  } catch (error) {
    return handleApiError(error);
  }
}
