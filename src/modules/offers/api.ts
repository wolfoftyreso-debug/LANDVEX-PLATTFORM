import { db } from "@/modules/core/db";
import type { OfferStatus } from "@/modules/core/types";

export interface Offer {
  id: string;
  rfq_id: string;
  company_id: string;
  price: number;
  currency: string;
  description: string;
  valid_until: string | null;
  estimated_start: string | null;
  estimated_days: number | null;
  status: OfferStatus;
  created_at: string;
  // joined
  companies?: {
    id: string;
    name: string;
    slug: string;
    logo_url: string | null;
    country: string;
    trust_score: number;
    rating_avg: number;
    rating_count: number;
    verification_level: string;
  };
  rfqs?: { id: string; title: string; status: string; customer_id: string };
}

export interface OfferInput {
  rfq_id: string;
  company_id: string;
  price: number;
  currency?: string;
  description: string;
  valid_until?: string | null;
  estimated_start?: string | null;
  estimated_days?: number | null;
}

const OFFER_SELECT =
  "*, companies(id, name, slug, logo_url, country, trust_score, rating_avg, rating_count, verification_level)";

export async function submitOffer(input: OfferInput): Promise<Offer> {
  const { data, error } = await db
    .from("offers")
    .insert(input)
    .select()
    .single();
  if (error) throw error;
  return data as Offer;
}

export async function listOffersForRfq(rfqId: string): Promise<Offer[]> {
  const { data, error } = await db
    .from("offers")
    .select(OFFER_SELECT)
    .eq("rfq_id", rfqId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Offer[];
}

export async function listCompanyOffers(companyId: string): Promise<Offer[]> {
  const { data, error } = await db
    .from("offers")
    .select("*, rfqs(id, title, status, customer_id)")
    .eq("company_id", companyId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Offer[];
}

export async function withdrawOffer(id: string): Promise<void> {
  const { error } = await db
    .from("offers")
    .update({ status: "withdrawn" })
    .eq("id", id);
  if (error) throw error;
}

/** Accept an offer transactionally (rejects siblings, creates the order) */
export async function acceptOffer(offerId: string): Promise<string> {
  const { data, error } = await db.rpc("accept_offer", { _offer_id: offerId });
  if (error) throw error;
  return data as string;
}
