import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { users } from "@/modules/identity/schema";
import { verifyPassword } from "@/modules/identity/password";
import type { Actor, Role } from "@/modules/identity/rbac";

/**
 * Auth.js (Section 3). Password sign-in is live for the ops team; the
 * magic-link email flow plugs into the same EmailProvider interface
 * (modules/notifications/email.ts) as a follow-up.
 */
import { env } from "@/lib/env";

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: env.AUTH_SECRET,
  session: { strategy: "jwt" },
  trustHost: true,
  pages: { signIn: "/signin" },
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = String(credentials?.email ?? "").toLowerCase();
        const password = String(credentials?.password ?? "");
        if (!email || !password) return null;

        const user = await db.query.users.findFirst({
          where: eq(users.email, email),
        });
        if (!user || !user.active || user.deletedAt || !user.passwordHash) {
          return null;
        }
        const ok = await verifyPassword(password, user.passwordHash);
        if (!ok) return null;

        return { id: user.id, email: user.email, name: user.name, role: user.role };
      },
    }),
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        token.role = (user as { role?: Role }).role;
        token.userId = user.id;
      }
      return token;
    },
    session({ session, token }) {
      if (session.user) {
        (session.user as { role?: Role }).role = token.role as Role;
        (session.user as { id?: string }).id = token.userId as string;
      }
      return session;
    },
  },
});

/** Resolve the RBAC actor for the current request (null if signed out) */
export async function currentActor(): Promise<Actor | null> {
  const session = await auth();
  const user = session?.user as { id?: string; role?: Role } | undefined;
  if (!user?.id || !user.role) return null;
  return { userId: user.id, role: user.role };
}
