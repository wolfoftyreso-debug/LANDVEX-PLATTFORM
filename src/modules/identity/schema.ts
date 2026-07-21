import {
  boolean,
  pgEnum,
  pgTable,
  text,
  timestamp,
  uuid,
} from "drizzle-orm/pg-core";

export const userRole = pgEnum("user_role", [
  "admin",
  "ops",
  "supplier",
  "buyer",
]);

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  // PII: email address
  email: text("email").notNull().unique(),
  // PII: person name
  name: text("name"),
  role: userRole("role").notNull().default("buyer"),
  passwordHash: text("password_hash"),
  emailVerifiedAt: timestamp("email_verified_at", { withTimezone: true }),
  active: boolean("active").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  deletedAt: timestamp("deleted_at", { withTimezone: true }),
});

// Auth.js verification tokens (magic links)
export const verificationTokens = pgTable("auth_verification_tokens", {
  identifier: text("identifier").notNull(),
  token: text("token").notNull().unique(),
  expires: timestamp("expires", { withTimezone: true }).notNull(),
});
