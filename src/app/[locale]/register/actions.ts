"use server";

import { headers } from "next/headers";
import { rateLimit } from "@/lib/rate-limit";
import {
  EmailTakenError,
  registerUser,
} from "@/modules/identity/service";

export interface RegisterFormState {
  error?: "email_taken" | "rate_limited" | "invalid";
  ok?: boolean;
}

export async function registerAction(
  _prev: RegisterFormState,
  formData: FormData,
): Promise<RegisterFormState> {
  const headerList = await headers();
  const ip =
    headerList.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  const limited = rateLimit(`register:${ip}`, {
    limit: 10,
    windowMs: 60 * 60 * 1000,
  });
  if (!limited.allowed) return { error: "rate_limited" };

  try {
    await registerUser({
      email: String(formData.get("email") ?? ""),
      password: String(formData.get("password") ?? ""),
      name: String(formData.get("name") ?? ""),
      role: formData.get("role") === "supplier" ? "supplier" : "buyer",
    });
    return { ok: true };
  } catch (error) {
    if (error instanceof EmailTakenError) return { error: "email_taken" };
    return { error: "invalid" };
  }
}
