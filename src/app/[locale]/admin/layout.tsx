import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { auth, currentActor, signOut } from "@/lib/auth";
import { hasRole } from "@/modules/identity/rbac";
import type { ReactNode } from "react";

export const dynamic = "force-dynamic";

export default async function AdminLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const actor = await currentActor();
  if (!actor) redirect(`/${locale}/signin`);
  if (!hasRole(actor, "ops")) redirect(`/${locale}`);

  const session = await auth();
  const t = await getTranslations("nav");
  const common = await getTranslations("common");

  return (
    <div className="layout">
      <aside className="sidebar">
        <Link className="brand" href={`/${locale}/admin`}>
          Baltic<strong>Bridge</strong> ops
        </Link>
        <nav>
          <Link href={`/${locale}/admin`}>{t("dashboard")}</Link>
          <Link href={`/${locale}/admin/verification`}>{t("verification")}</Link>
          <Link href={`/${locale}/admin/queue`}>{t("reviewQueue")}</Link>
          <Link href={`/${locale}/admin/companies`}>{t("companies")}</Link>
          <Link href={`/${locale}/admin/rfqs`}>{t("rfqs")}</Link>
          <Link href={`/${locale}/admin/deals`}>{t("deals")}</Link>
          <Link href={`/${locale}/admin/tasks`}>{t("tasks")}</Link>
        </nav>
      </aside>
      <main className="main">
        <div className="topbar">
          <span className="muted">{session?.user?.email}</span>
          <form
            action={async () => {
              "use server";
              await signOut({ redirectTo: `/${locale}` });
            }}
          >
            <button className="secondary" type="submit">
              {common("signOut")}
            </button>
          </form>
        </div>
        {children}
      </main>
    </div>
  );
}
