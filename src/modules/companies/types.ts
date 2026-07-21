import type {
  AvailabilityStatus,
  VerificationLevel,
} from "@/modules/core/types";

export interface Company {
  id: string;
  owner_id: string;
  slug: string;
  name: string;
  description: string | null;
  logo_url: string | null;
  cover_url: string | null;
  country: string;
  region: string | null;
  city: string | null;
  address: string | null;
  countries_served: string[];
  languages: string[];
  contact_email: string | null;
  contact_phone: string | null;
  website: string | null;
  vat_number: string | null;
  org_number: string | null;
  year_founded: number | null;
  employee_count: number | null;
  certifications: string[];
  licenses: string[];
  insurance_info: string | null;
  availability: AvailabilityStatus;
  verification_level: VerificationLevel;
  identity_verified: boolean;
  vat_verified: boolean;
  trust_score: number;
  rating_avg: number;
  rating_count: number;
  completed_projects: number;
  repeat_customers: number;
  response_rate: number | null;
  avg_response_hours: number | null;
  created_at: string;
}

export interface PortfolioItem {
  id: string;
  company_id: string;
  title: string;
  description: string | null;
  image_url: string | null;
  created_at: string;
}

export interface CompanyServiceRow {
  id: string;
  company_id: string;
  category_id: string;
  categories?: { id: string; name: string; slug: string; vertical_id: string };
}

export interface CompanyFilters {
  search?: string;
  country?: string;
  categoryId?: string;
  verticalId?: string;
  verifiedOnly?: boolean;
  minRating?: number;
  language?: string;
}

export type CompanyInput = Pick<
  Company,
  "name" | "slug" | "country" | "description"
> &
  Partial<
    Omit<
      Company,
      | "id"
      | "owner_id"
      | "trust_score"
      | "rating_avg"
      | "rating_count"
      | "completed_projects"
      | "repeat_customers"
      | "verification_level"
      | "identity_verified"
      | "vat_verified"
      | "created_at"
    >
  >;
