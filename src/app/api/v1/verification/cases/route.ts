import { z } from "zod";
import {
  handleApiError,
  parseBody,
  requireApiActor,
  withIdempotency,
} from "@/lib/api";
import { openCase } from "@/modules/verification/service";

export const dynamic = "force-dynamic";

const openCaseSchema = z.object({
  companyId: z.string().uuid(),
  corridorId: z.string().uuid(),
  workerIds: z.array(z.string().uuid()).optional(),
});

export async function POST(request: Request) {
  try {
    const actor = await requireApiActor();
    const input = parseBody(openCaseSchema, await request.json());

    return withIdempotency(request, input, async () => {
      const created = await openCase(actor, input);
      return { status: 201, body: { data: created } };
    });
  } catch (error) {
    return handleApiError(error);
  }
}
