import { eq } from "drizzle-orm";
import { z } from "zod";
import { db } from "@/lib/db";
import { appendOutbox, writeAudit } from "@/modules/audit/service";
import { users } from "./schema";
import { hashPassword } from "./password";
import type { Role } from "./rbac";

export type User = typeof users.$inferSelect;

export const registerInputSchema = z.object({
  email: z.string().email().max(254),
  password: z.string().min(10).max(200),
  name: z.string().min(1).max(120),
  /** Self-serve signup only creates marketplace roles — never admin/ops */
  role: z.enum(["buyer", "supplier"]),
});

export type RegisterInput = z.infer<typeof registerInputSchema>;

export class EmailTakenError extends Error {
  constructor() {
    super("An account with this email already exists");
    this.name = "EmailTakenError";
  }
}

/**
 * Self-serve registration (Alibaba model): customers sign up as `buyer`,
 * companies sign up as `supplier` and then create their company profile.
 * admin/ops accounts are provisioned internally, never via this path.
 */
export async function registerUser(input: RegisterInput): Promise<User> {
  const parsed = registerInputSchema.parse(input);
  const email = parsed.email.toLowerCase();

  const existing = await db.query.users.findFirst({
    where: eq(users.email, email),
  });
  if (existing) throw new EmailTakenError();

  const passwordHash = await hashPassword(parsed.password);

  return db.transaction(async (tx) => {
    const [user] = await tx
      .insert(users)
      .values({
        email,
        name: parsed.name,
        role: parsed.role as Role,
        passwordHash,
        // Password signup: e-mail ownership is confirmed via the magic-link
        // flow when EMAIL_PROVIDER=ses; console provider logs the link in dev.
        emailVerifiedAt: null,
      })
      .returning();
    if (!user) throw new Error("User insert failed");

    await writeAudit(tx, {
      actorId: user.id,
      entityType: "user",
      entityId: user.id,
      action: "user.registered",
      after: { role: parsed.role },
    });
    await appendOutbox(tx, "identity.user_registered", {
      userId: user.id,
      role: parsed.role,
    });
    return user;
  });
}

export async function getUserById(id: string): Promise<User | undefined> {
  return db.query.users.findFirst({ where: eq(users.id, id) });
}

export async function getUserByEmail(email: string): Promise<User | undefined> {
  return db.query.users.findFirst({
    where: eq(users.email, email.toLowerCase()),
  });
}
