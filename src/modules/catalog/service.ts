import { asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { corridors, requirementDefinitions, trades } from "./schema";

export type RequirementDefinition =
  typeof requirementDefinitions.$inferSelect;
export type Corridor = typeof corridors.$inferSelect;
export type Trade = typeof trades.$inferSelect;

export async function listCorridors(): Promise<Corridor[]> {
  return db.select().from(corridors).orderBy(asc(corridors.slug));
}

export async function listTrades(): Promise<Trade[]> {
  return db.select().from(trades).orderBy(asc(trades.slug));
}

export async function getCorridorBySlug(slug: string): Promise<Corridor | undefined> {
  return db.query.corridors.findFirst({ where: eq(corridors.slug, slug) });
}

export async function getRequirementsForCorridor(
  corridorId: string,
): Promise<RequirementDefinition[]> {
  return db
    .select()
    .from(requirementDefinitions)
    .where(eq(requirementDefinitions.corridorId, corridorId))
    .orderBy(asc(requirementDefinitions.sortOrder));
}
