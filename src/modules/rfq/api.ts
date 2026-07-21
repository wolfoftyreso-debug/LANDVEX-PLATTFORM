import { db, supabase } from "@/modules/core/db";
import type { Rfq, RfqFilters, RfqInput } from "./types";

const RFQ_SELECT =
  "*, verticals(slug, name), categories(name, slug), rfq_images(id, image_url)";

export async function createRfq(
  input: RfqInput,
  imageUrls: string[] = [],
): Promise<Rfq> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) throw new Error("You must be signed in to request quotes");

  const { data, error } = await db
    .from("rfqs")
    .insert({ ...input, customer_id: userId })
    .select()
    .single();
  if (error) throw error;

  if (imageUrls.length > 0) {
    const { error: imgError } = await db
      .from("rfq_images")
      .insert(imageUrls.map((image_url) => ({ rfq_id: data.id, image_url })));
    if (imgError) throw imgError;
  }
  return data as Rfq;
}

export async function getRfq(id: string): Promise<Rfq | null> {
  const { data, error } = await db
    .from("rfqs")
    .select(RFQ_SELECT)
    .eq("id", id)
    .maybeSingle();
  if (error) throw error;
  return data as Rfq | null;
}

export async function listMyRfqs(): Promise<Rfq[]> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) return [];

  const { data, error } = await db
    .from("rfqs")
    .select(RFQ_SELECT)
    .eq("customer_id", userId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Rfq[];
}

/** Open RFQs for companies to browse (the lead inbox) */
export async function listOpenRfqs(filters: RfqFilters = {}): Promise<Rfq[]> {
  let query = db
    .from("rfqs")
    .select(RFQ_SELECT)
    .eq("status", "published")
    .order("created_at", { ascending: false })
    .limit(60);

  if (filters.verticalId) query = query.eq("vertical_id", filters.verticalId);
  if (filters.categoryId) query = query.eq("category_id", filters.categoryId);
  if (filters.country) query = query.eq("country", filters.country);

  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Rfq[];
}

export async function withdrawRfq(id: string): Promise<void> {
  const { error } = await db
    .from("rfqs")
    .update({ status: "withdrawn" })
    .eq("id", id);
  if (error) throw error;
}
