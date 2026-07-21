import { db, supabase } from "@/modules/core/db";
import type {
  Company,
  CompanyFilters,
  CompanyInput,
  CompanyServiceRow,
  PortfolioItem,
} from "./types";

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 60);
}

export async function listCompanies(
  filters: CompanyFilters = {},
): Promise<Company[]> {
  const sortColumn =
    filters.sort === "rating"
      ? "rating_avg"
      : filters.sort === "newest"
        ? "created_at"
        : "trust_score";

  let query = db
    .from("companies")
    .select("*")
    .order(sortColumn, { ascending: false })
    .limit(60);

  if (filters.country) query = query.eq("country", filters.country);
  if (filters.verifiedOnly) query = query.neq("verification_level", "unverified");
  if (filters.minRating) query = query.gte("rating_avg", filters.minRating);
  if (filters.language) query = query.contains("languages", [filters.language]);
  if (filters.search) query = query.ilike("name", `%${filters.search}%`);

  if (filters.categoryId) {
    const { data: serviceRows, error: svcError } = await db
      .from("company_services")
      .select("company_id")
      .eq("category_id", filters.categoryId);
    if (svcError) throw svcError;
    const ids = (serviceRows ?? []).map(
      (r: { company_id: string }) => r.company_id,
    );
    if (ids.length === 0) return [];
    query = query.in("id", ids);
  }

  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Company[];
}

export async function getCompanyBySlug(slug: string): Promise<Company | null> {
  const { data, error } = await db
    .from("companies")
    .select("*")
    .eq("slug", slug)
    .maybeSingle();
  if (error) throw error;
  return data as Company | null;
}

export async function getMyCompany(): Promise<Company | null> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) return null;

  const { data, error } = await db
    .from("companies")
    .select("*")
    .eq("owner_id", userId)
    .maybeSingle();
  if (error) throw error;
  if (data) return data as Company;

  const { data: membership } = await db
    .from("company_members")
    .select("company_id")
    .eq("user_id", userId)
    .maybeSingle();
  if (!membership) return null;

  const { data: memberCompany, error: mcError } = await db
    .from("companies")
    .select("*")
    .eq("id", membership.company_id)
    .maybeSingle();
  if (mcError) throw mcError;
  return memberCompany as Company | null;
}

export async function createCompany(input: CompanyInput): Promise<Company> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) throw new Error("You must be signed in to register a company");

  const { data, error } = await db
    .from("companies")
    .insert({ ...input, owner_id: userId })
    .select()
    .single();
  if (error) throw error;
  return data as Company;
}

export async function updateCompany(
  id: string,
  patch: Partial<CompanyInput>,
): Promise<Company> {
  const { data, error } = await db
    .from("companies")
    .update(patch)
    .eq("id", id)
    .select()
    .single();
  if (error) throw error;
  return data as Company;
}

export async function setCompanyServices(
  companyId: string,
  categoryIds: string[],
): Promise<void> {
  const { error: deleteError } = await db
    .from("company_services")
    .delete()
    .eq("company_id", companyId);
  if (deleteError) throw deleteError;
  if (categoryIds.length === 0) return;
  const { error } = await db
    .from("company_services")
    .insert(categoryIds.map((category_id) => ({ company_id: companyId, category_id })));
  if (error) throw error;
}

export async function listCompanyServices(
  companyId: string,
): Promise<CompanyServiceRow[]> {
  const { data, error } = await db
    .from("company_services")
    .select("*, categories(id, name, slug, vertical_id)")
    .eq("company_id", companyId);
  if (error) throw error;
  return (data ?? []) as CompanyServiceRow[];
}

export async function listPortfolio(
  companyId: string,
): Promise<PortfolioItem[]> {
  const { data, error } = await db
    .from("portfolio_items")
    .select("*")
    .eq("company_id", companyId)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as PortfolioItem[];
}

export async function addPortfolioItem(
  companyId: string,
  item: { title: string; description?: string; image_url?: string },
): Promise<PortfolioItem> {
  const { data, error } = await db
    .from("portfolio_items")
    .insert({ company_id: companyId, ...item })
    .select()
    .single();
  if (error) throw error;
  return data as PortfolioItem;
}

/** Upload to the media bucket; path is namespaced by user id per RLS policy */
export async function uploadMedia(
  bucket: "company-media" | "rfq-media",
  file: File,
): Promise<string> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) throw new Error("You must be signed in to upload files");

  const ext = file.name.split(".").pop() ?? "bin";
  const path = `${userId}/${crypto.randomUUID()}.${ext}`;
  const { error } = await supabase.storage.from(bucket).upload(path, file);
  if (error) throw error;
  const { data } = supabase.storage.from(bucket).getPublicUrl(path);
  return data.publicUrl;
}
