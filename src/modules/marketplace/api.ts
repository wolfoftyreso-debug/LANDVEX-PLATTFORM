import { db } from "@/modules/core/db";
import type { Vertical, Category } from "@/modules/core/types";

export async function listVerticals(): Promise<Vertical[]> {
  const { data, error } = await db
    .from("verticals")
    .select("*")
    .eq("active", true)
    .order("sort_order");
  if (error) throw error;
  return (data ?? []) as Vertical[];
}

export async function listCategories(verticalId?: string): Promise<Category[]> {
  let query = db.from("categories").select("*").order("sort_order");
  if (verticalId) query = query.eq("vertical_id", verticalId);
  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Category[];
}
