import { getTranslations, setRequestLocale } from "next-intl/server";
import { and, eq, gte, isNull, lte } from "drizzle-orm";
import { db } from "@/lib/db";
import { companies } from "@/modules/companies/schema";
import {
  opsTasks,
  verificationItems,
} from "@/modules/verification/schema";
import { listCasesByState } from "@/modules/verification/service";

export const dynamic = "force-dynamic";

export default async function AdminDashboard({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("dashboard");
  const tState = await getTranslations("caseState");

  const [cases, allCompanies, openTasks, expiring] = await Promise.all([
    listCasesByState(),
    db.select({ id: companies.id }).from(companies).where(isNull(companies.deletedAt)),
    db.select({ id: opsTasks.id }).from(opsTasks).where(eq(opsTasks.status, "open")),
    db
      .select({ id: verificationItems.id })
      .from(verificationItems)
      .where(
        and(
          eq(verificationItems.status, "approved"),
          gte(verificationItems.validUntil, new Date()),
          lte(
            verificationItems.validUntil,
            new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
          ),
        ),
      ),
  ]);

  return (
    <div>
      <h1>{t("title")}</h1>

      <div className="grid cols-4 mt">
        <div className="card stat">
          <div className="value">{allCompanies.length}</div>
          <div className="label">{t("companies")}</div>
        </div>
        <div className="card stat">
          <div className="value">{cases.in_review.length}</div>
          <div className="label">{tState("in_review")}</div>
        </div>
        <div className="card stat">
          <div className="value">{openTasks.length}</div>
          <div className="label">{t("openTasks")}</div>
        </div>
        <div className="card stat">
          <div className="value">{expiring.length}</div>
          <div className="label">{t("expiringSoon")}</div>
        </div>
      </div>

      <h2>{t("casesByState")}</h2>
      <div className="grid cols-5">
        {(Object.keys(cases) as (keyof typeof cases)[]).map((state) => (
          <div key={state} className="card stat">
            <div className="value">{cases[state].length}</div>
            <div className="label">
              <span className={`badge ${state}`}>{tState(state)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
