"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";
import { currentActor } from "@/lib/auth";
import { requireRole } from "@/modules/identity/rbac";
import { addWorker, createCompany } from "@/modules/companies/service";

export async function createMyCompanyAction(formData: FormData) {
  const actor = requireRole(await currentActor(), "supplier");
  await createCompany(actor, {
    name: z.string().min(2).parse(formData.get("name")),
    country: z
      .string()
      .length(2)
      .parse(String(formData.get("country") ?? "").toUpperCase()),
    registrationNumber: String(formData.get("registrationNumber") ?? "") || undefined,
    vatNumber: String(formData.get("vatNumber") ?? "") || undefined,
    city: String(formData.get("city") ?? "") || undefined,
    description: String(formData.get("description") ?? "") || undefined,
  });
  revalidatePath("/[locale]/portal", "page");
}

export async function addMyWorkerAction(formData: FormData) {
  const actor = requireRole(await currentActor(), "supplier");
  await addWorker(actor, {
    companyId: z.string().uuid().parse(formData.get("companyId")),
    name: z.string().min(1).parse(formData.get("name")),
    tradeRole: String(formData.get("tradeRole") ?? "") || undefined,
  });
  revalidatePath("/[locale]/portal", "page");
}
