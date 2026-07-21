import { db, supabase } from "@/modules/core/db";
import type { OrderStatus } from "@/modules/core/types";

export interface MarketplaceOrder {
  id: string;
  rfq_id: string;
  offer_id: string;
  company_id: string;
  customer_id: string;
  amount: number;
  currency: string;
  status: OrderStatus;
  created_at: string;
  completed_at: string | null;
  // joined
  companies?: { id: string; name: string; slug: string; logo_url: string | null };
  rfqs?: { id: string; title: string };
  reviews?: { id: string }[];
}

const ORDER_SELECT =
  "*, companies(id, name, slug, logo_url), rfqs(id, title), reviews(id)";

export async function listMyCustomerOrders(): Promise<MarketplaceOrder[]> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) return [];

  const { data, error } = await db
    .from("marketplace_orders")
    .select(ORDER_SELECT)
    .eq("customer_id", userId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as MarketplaceOrder[];
}

export async function listCompanyOrders(
  companyId: string,
): Promise<MarketplaceOrder[]> {
  const { data, error } = await db
    .from("marketplace_orders")
    .select(ORDER_SELECT)
    .eq("company_id", companyId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as MarketplaceOrder[];
}

export async function getOrder(id: string): Promise<MarketplaceOrder | null> {
  const { data, error } = await db
    .from("marketplace_orders")
    .select(ORDER_SELECT)
    .eq("id", id)
    .maybeSingle();
  if (error) throw error;
  return data as MarketplaceOrder | null;
}

export async function updateOrderStatus(
  id: string,
  status: OrderStatus,
): Promise<void> {
  const { error } = await db
    .from("marketplace_orders")
    .update({ status })
    .eq("id", id);
  if (error) throw error;
}
