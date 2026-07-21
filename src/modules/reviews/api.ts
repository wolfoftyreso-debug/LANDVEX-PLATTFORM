import { db, supabase } from "@/modules/core/db";

export interface Review {
  id: string;
  order_id: string;
  company_id: string;
  customer_id: string;
  rating_overall: number;
  rating_communication: number | null;
  rating_quality: number | null;
  rating_price: number | null;
  rating_delivery: number | null;
  rating_professionalism: number | null;
  would_recommend: boolean;
  comment: string | null;
  project_description: string | null;
  photos: string[];
  created_at: string;
}

export interface ReviewInput {
  order_id: string;
  company_id: string;
  rating_overall: number;
  rating_communication?: number;
  rating_quality?: number;
  rating_price?: number;
  rating_delivery?: number;
  rating_professionalism?: number;
  would_recommend: boolean;
  comment?: string;
  project_description?: string;
  photos?: string[];
}

export async function listCompanyReviews(companyId: string): Promise<Review[]> {
  const { data, error } = await db
    .from("reviews")
    .select("*")
    .eq("company_id", companyId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Review[];
}

export async function createReview(input: ReviewInput): Promise<Review> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) throw new Error("You must be signed in to leave a review");

  const { data, error } = await db
    .from("reviews")
    .insert({ ...input, customer_id: userId })
    .select()
    .single();
  if (error) throw error;
  return data as Review;
}
