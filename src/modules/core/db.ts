import { supabase } from "@/integrations/supabase/client";
import type { SupabaseClient } from "@supabase/supabase-js";

// The marketplace schema is newer than the generated Database types in
// src/integrations/supabase/types.ts. Until those are regenerated from the
// live database, marketplace tables are accessed through this handle and
// each module's API layer declares precise domain types on its returns.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const db = supabase as unknown as SupabaseClient<any, "public", any>;

export { supabase };
