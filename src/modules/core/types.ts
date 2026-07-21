// Shared marketplace domain types (mirror supabase enums)

export type VerificationLevel =
  | "unverified"
  | "bronze"
  | "silver"
  | "gold"
  | "platinum";

export type AvailabilityStatus = "available" | "busy" | "unavailable";

export type RfqStatus =
  | "draft"
  | "published"
  | "accepted"
  | "expired"
  | "withdrawn";

export type OfferStatus = "submitted" | "withdrawn" | "accepted" | "rejected";

export type OrderStatus =
  | "created"
  | "in_progress"
  | "delivered"
  | "completed"
  | "disputed"
  | "cancelled";

export interface Vertical {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  icon: string | null;
  active: boolean;
  sort_order: number;
}

export interface Category {
  id: string;
  vertical_id: string;
  slug: string;
  name: string;
  parent_id: string | null;
  sort_order: number;
}

export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}
