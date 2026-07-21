import { NextResponse } from "next/server";
import { z } from "zod";
import {
  handleApiError,
  parseBody,
  requireApiActor,
  withIdempotency,
} from "@/lib/api";
import { createCompany, listCompanies } from "@/modules/companies/service";

export const dynamic = "force-dynamic";

const createCompanySchema = z.object({
  name: z.string().min(2),
  country: z.string().length(2),
  registrationNumber: z.string().optional(),
  vatNumber: z.string().optional(),
  city: z.string().optional(),
  description: z.string().optional(),
  yearFounded: z.number().int().min(1800).max(2100).optional(),
  headcount: z.number().int().min(1).optional(),
  languages: z.array(z.string()).optional(),
});

export async function GET() {
  try {
    await requireApiActor();
    const companies = await listCompanies();
    return NextResponse.json({ data: companies });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function POST(request: Request) {
  try {
    const actor = await requireApiActor();
    const raw = await request.json();
    const input = parseBody(createCompanySchema, raw);

    return withIdempotency(request, input, async () => {
      const company = await createCompany(actor, input);
      return { status: 201, body: { data: company } };
    });
  } catch (error) {
    return handleApiError(error);
  }
}
