import { db } from "@/modules/core/db";
import type { VerificationLevel } from "@/modules/core/types";

export interface VerificationRequest {
  id: string;
  company_id: string;
  requested_level: VerificationLevel;
  documents: { name: string; url?: string }[];
  status: "pending" | "approved" | "rejected";
  notes: string | null;
  created_at: string;
  reviewed_at: string | null;
  // from the verification_queue view (admin)
  company_name?: string;
  company_slug?: string;
  company_country?: string;
  vat_number?: string | null;
  org_number?: string | null;
}

export const LEVEL_ORDER: VerificationLevel[] = [
  "bronze",
  "silver",
  "gold",
  "platinum",
];

export function nextLevel(current: VerificationLevel): VerificationLevel | null {
  if (current === "unverified") return "bronze";
  const idx = LEVEL_ORDER.indexOf(current);
  return idx >= 0 && idx < LEVEL_ORDER.length - 1 ? LEVEL_ORDER[idx + 1] : null;
}

export async function listCompanyVerificationRequests(
  companyId: string,
): Promise<VerificationRequest[]> {
  const { data, error } = await db
    .from("verification_requests")
    .select("*")
    .eq("company_id", companyId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as VerificationRequest[];
}

export async function requestVerification(
  companyId: string,
  level: VerificationLevel,
  documents: { name: string; url?: string }[] = [],
): Promise<void> {
  const { error } = await db.from("verification_requests").insert({
    company_id: companyId,
    requested_level: level,
    documents,
  });
  if (error) throw error;
}

/** Admin: pending queue with company details */
export async function listVerificationQueue(): Promise<VerificationRequest[]> {
  const { data, error } = await db
    .from("verification_queue")
    .select("*")
    .eq("status", "pending")
    .order("created_at", { ascending: true });
  if (error) throw error;
  return (data ?? []) as VerificationRequest[];
}

export async function reviewVerification(
  requestId: string,
  approve: boolean,
  notes?: string,
): Promise<void> {
  const { error } = await db.rpc("review_verification", {
    _request_id: requestId,
    _approve: approve,
    _notes: notes ?? null,
  });
  if (error) throw error;
}

export async function isAdmin(): Promise<boolean> {
  const { data, error } = await db.rpc("is_admin");
  if (error) return false;
  return data === true;
}
