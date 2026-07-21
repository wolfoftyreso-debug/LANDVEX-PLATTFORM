import { db } from "@/modules/core/db";

export type PaymentStatus =
  | "pending"
  | "held_in_escrow"
  | "released"
  | "refunded"
  | "cancelled";

export interface OrderPayment {
  id: string;
  order_id: string;
  amount: number;
  currency: string;
  status: PaymentStatus;
  provider: string;
  provider_reference: string | null;
  paid_at: string | null;
  released_at: string | null;
  created_at: string;
}

export async function getOrderPayment(
  orderId: string,
): Promise<OrderPayment | null> {
  const { data, error } = await db
    .from("order_payments")
    .select("*")
    .eq("order_id", orderId)
    .maybeSingle();
  if (error) throw error;
  return data as OrderPayment | null;
}

/** Secure the order amount in escrow (manual provider until a PSP is wired in) */
export async function payOrderEscrow(orderId: string): Promise<void> {
  const { error } = await db.rpc("pay_order_escrow", { _order_id: orderId });
  if (error) throw error;
}

/** Admin: refund an escrowed payment during dispute resolution */
export async function refundOrderPayment(
  orderId: string,
  reason?: string,
): Promise<void> {
  const { error } = await db.rpc("refund_order_payment", {
    _order_id: orderId,
    _reason: reason ?? null,
  });
  if (error) throw error;
}
