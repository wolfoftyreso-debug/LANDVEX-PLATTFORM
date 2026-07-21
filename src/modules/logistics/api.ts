import { db, supabase } from "@/modules/core/db";

export type ShipmentStatus =
  | "requested"
  | "booked"
  | "picked_up"
  | "in_transit"
  | "delivered"
  | "cancelled";

export interface Shipment {
  id: string;
  reference_type: string;
  reference_id: string | null;
  requester_id: string;
  counterpart_company_id: string | null;
  pickup_address: string;
  pickup_country: string;
  delivery_address: string;
  delivery_country: string;
  insured: boolean;
  provider: string | null;
  tracking_code: string | null;
  price: number | null;
  currency: string;
  estimated_delivery: string | null;
  status: ShipmentStatus;
  created_at: string;
}

export interface ShipmentInput {
  reference_id: string;
  counterpart_company_id?: string | null;
  pickup_address: string;
  pickup_country: string;
  delivery_address: string;
  delivery_country: string;
  insured?: boolean;
}

export const SHIPMENT_FLOW: ShipmentStatus[] = [
  "requested",
  "booked",
  "picked_up",
  "in_transit",
  "delivered",
];

export async function listShipmentsForOrder(
  orderId: string,
): Promise<Shipment[]> {
  const { data, error } = await db
    .from("shipments")
    .select("*")
    .eq("reference_type", "marketplace_order")
    .eq("reference_id", orderId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Shipment[];
}

export async function requestShipment(input: ShipmentInput): Promise<Shipment> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) throw new Error("You must be signed in to request transport");

  const { data, error } = await db
    .from("shipments")
    .insert({
      ...input,
      requester_id: userId,
      reference_type: "marketplace_order",
    })
    .select()
    .single();
  if (error) throw error;
  return data as Shipment;
}

export async function updateShipmentStatus(
  id: string,
  status: ShipmentStatus,
): Promise<void> {
  const { error } = await db.from("shipments").update({ status }).eq("id", id);
  if (error) throw error;
}
