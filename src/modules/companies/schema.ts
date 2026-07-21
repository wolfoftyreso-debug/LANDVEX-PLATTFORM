import {
  integer,
  pgEnum,
  pgTable,
  text,
  timestamp,
  uuid,
} from "drizzle-orm/pg-core";
import { users } from "@/modules/identity/schema";

export const companies = pgTable("companies", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  country: text("country").notNull(), // ISO 3166-1 alpha-2, e.g. "LT"
  registrationNumber: text("registration_number"), // national registry no
  vatNumber: text("vat_number"),
  description: text("description"),
  city: text("city"),
  // PII-adjacent contact data lives on contacts, not here
  website: text("website"),
  yearFounded: integer("year_founded"),
  headcount: integer("headcount"),
  languages: text("languages").array().notNull().default([]),
  ownerUserId: uuid("owner_user_id").references(() => users.id),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  deletedAt: timestamp("deleted_at", { withTimezone: true }),
});

/** Permanent slugs; renames append a new row and old slugs redirect */
export const companySlugs = pgTable("company_slugs", {
  id: uuid("id").primaryKey().defaultRandom(),
  companyId: uuid("company_id")
    .notNull()
    .references(() => companies.id),
  slug: text("slug").notNull().unique(),
  isPrimary: integer("is_primary").notNull().default(1),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const contacts = pgTable("contacts", {
  id: uuid("id").primaryKey().defaultRandom(),
  companyId: uuid("company_id")
    .notNull()
    .references(() => companies.id),
  // PII: person name
  name: text("name").notNull(),
  // PII: email
  email: text("email"),
  // PII: phone
  phone: text("phone"),
  roleTitle: text("role_title"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  deletedAt: timestamp("deleted_at", { withTimezone: true }),
});

export const workers = pgTable("workers", {
  id: uuid("id").primaryKey().defaultRandom(),
  companyId: uuid("company_id")
    .notNull()
    .references(() => companies.id),
  // PII: person name
  name: text("name").notNull(),
  // PII: national/person identifier where required for compliance docs
  personIdentifier: text("person_identifier"),
  tradeRole: text("trade_role"), // e.g. "welder", "fitter"
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  deletedAt: timestamp("deleted_at", { withTimezone: true }),
});

export const capacityStatus = pgEnum("capacity_status", [
  "draft",
  "published",
  "archived",
]);

/** M2 uses these publicly; ops can create them from day one */
export const capacityListings = pgTable("capacity_listings", {
  id: uuid("id").primaryKey().defaultRandom(),
  companyId: uuid("company_id")
    .notNull()
    .references(() => companies.id),
  tradeId: uuid("trade_id").notNull(),
  headcount: integer("headcount").notNull(),
  certificationsSummary: text("certifications_summary"),
  earliestStart: timestamp("earliest_start", { withTimezone: true }),
  weeksAvailable: integer("weeks_available"),
  baseLocation: text("base_location"),
  status: capacityStatus("status").notNull().default("draft"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});
