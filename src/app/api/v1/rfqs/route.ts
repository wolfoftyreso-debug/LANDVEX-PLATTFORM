import { z } from "zod";
import { apiError, handleApiError, parseBody, withIdempotency } from "@/lib/api";
import { rateLimit } from "@/lib/rate-limit";
import { currentActor } from "@/lib/auth";
import {
  createRfq,
  findOrCreateBuyer,
  rfqInputSchema,
} from "@/modules/rfq/service";

export const dynamic = "force-dynamic";

const publicRfqSchema = rfqInputSchema.extend({
  buyerEmail: z.string().email().optional(),
  buyerName: z.string().min(1).max(120).optional(),
});

/**
 * Buyer RFQ intake — public + logged-in (Section 5/M3). Anonymous
 * submissions auto-create a buyer account from the email.
 */
export async function POST(request: Request) {
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  const limited = rateLimit(`rfq:${ip}`, { limit: 20, windowMs: 60 * 60 * 1000 });
  if (!limited.allowed) {
    return apiError(429, "Too many requests — try again later");
  }

  try {
    const input = parseBody(publicRfqSchema, await request.json());
    const actor = await currentActor();

    let buyerUserId: string;
    if (actor) {
      buyerUserId = actor.userId;
    } else {
      if (!input.buyerEmail || !input.buyerName) {
        return apiError(400, "buyerEmail and buyerName are required when not signed in");
      }
      const buyer = await findOrCreateBuyer(input.buyerEmail, input.buyerName);
      buyerUserId = buyer.userId;
    }

    return await withIdempotency(request, input, async () => {
      const rfq = await createRfq(buyerUserId, input);
      return { status: 201, body: { data: { id: rfq.id, status: rfq.status } } };
    });
  } catch (error) {
    return handleApiError(error);
  }
}
