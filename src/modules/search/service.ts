import { sql } from "drizzle-orm";
import { db } from "@/lib/db";

/**
 * Search module — read model over public supplier data (Postgres FTS +
 * trigram per Section 3). Read-only projection: it never mutates other
 * modules' tables; writes stay behind their service interfaces.
 */

export interface SupplierSearchHit {
  companyId: string;
  name: string;
  slug: string | null;
  country: string;
  city: string | null;
  description: string | null;
  languages: string[];
  yearFounded: number | null;
  headcount: number | null;
  verified: boolean;
  rank: number;
}

export interface SupplierSearchParams {
  q?: string;
  country?: string;
  language?: string;
  verifiedOnly?: boolean;
  limit?: number;
}

export async function searchSuppliers(
  params: SupplierSearchParams,
): Promise<SupplierSearchHit[]> {
  const limit = Math.min(params.limit ?? 30, 100);
  const q = params.q?.trim() ?? "";

  const rows = await db.execute(sql`
    SELECT
      c.id AS company_id,
      c.name,
      c.country,
      c.city,
      c.description,
      c.languages,
      c.year_founded,
      c.headcount,
      (SELECT s.slug FROM company_slugs s
        WHERE s.company_id = c.id AND s.is_primary = 1
        ORDER BY s.created_at DESC LIMIT 1) AS slug,
      EXISTS (
        SELECT 1 FROM verification_cases vc
        WHERE vc.company_id = c.id AND vc.state = 'verified'
      ) AS verified,
      CASE
        WHEN ${q} = '' THEN 0
        ELSE COALESCE(ts_rank(c.search_tsv, websearch_to_tsquery('simple', ${q})), 0)
             + similarity(c.name, ${q})
      END AS rank
    FROM companies c
    WHERE c.deleted_at IS NULL
      AND (
        ${q} = ''
        OR c.search_tsv @@ websearch_to_tsquery('simple', ${q})
        OR c.name % ${q}
      )
      AND (${params.country ?? ""} = '' OR c.country = ${params.country ?? ""})
      AND (${params.language ?? ""} = '' OR ${params.language ?? ""} = ANY (c.languages))
      AND (
        ${params.verifiedOnly ?? false} = false
        OR EXISTS (
          SELECT 1 FROM verification_cases vc
          WHERE vc.company_id = c.id AND vc.state = 'verified'
        )
      )
    ORDER BY verified DESC, rank DESC, c.name ASC
    LIMIT ${limit}
  `);

  return (rows.rows as Record<string, unknown>[]).map((row) => ({
    companyId: String(row.company_id),
    name: String(row.name),
    slug: row.slug ? String(row.slug) : null,
    country: String(row.country),
    city: row.city ? String(row.city) : null,
    description: row.description ? String(row.description) : null,
    languages: (row.languages as string[]) ?? [],
    yearFounded: row.year_founded == null ? null : Number(row.year_founded),
    headcount: row.headcount == null ? null : Number(row.headcount),
    verified: row.verified === true,
    rank: Number(row.rank ?? 0),
  }));
}
