import type { RfqStatus } from "@/modules/core/types";

export interface Rfq {
  id: string;
  customer_id: string;
  vertical_id: string;
  category_id: string | null;
  title: string;
  description: string;
  country: string;
  region: string | null;
  city: string | null;
  address: string | null;
  budget_min: number | null;
  budget_max: number | null;
  currency: string;
  deadline: string | null;
  preferred_language: string | null;
  metadata: Record<string, string>;
  metadata_schema_version: number;
  status: RfqStatus;
  created_at: string;
  // joined
  verticals?: { slug: string; name: string };
  categories?: { name: string; slug: string } | null;
  rfq_images?: { id: string; image_url: string }[];
}

export interface RfqInput {
  vertical_id: string;
  category_id?: string | null;
  title: string;
  description: string;
  country: string;
  region?: string;
  city?: string;
  address?: string;
  budget_min?: number | null;
  budget_max?: number | null;
  currency?: string;
  deadline?: string | null;
  preferred_language?: string | null;
  metadata?: Record<string, string>;
  metadata_schema_version?: number;
}

export interface RfqFilters {
  verticalId?: string;
  categoryId?: string;
  country?: string;
}
