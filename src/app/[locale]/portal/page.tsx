import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { and, eq, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { auth, currentActor, signOut } from "@/lib/auth";
import {
  getCompanyByOwner,
  getPrimarySlug,
  listCompanyCapacity,
  listWorkers,
} from "@/modules/companies/service";
import { listTrades } from "@/modules/catalog/service";
import UploadEvidence from "./upload-evidence";
import {
  archiveMyCapacityAction,
  createMyCapacityAction,
  updateMyProfileAction,
} from "./actions";
import { LANGUAGE_OPTIONS } from "./languages";
import { requirementDefinitions } from "@/modules/catalog/schema";
import {
  verificationCases,
  verificationItems,
} from "@/modules/verification/schema";
import { badgeVisible, type CaseState } from "@/modules/verification/domain";
import { hasRole } from "@/modules/identity/rbac";
import { addMyWorkerAction, createMyCompanyAction } from "./actions";

export const dynamic = "force-dynamic";

/**
 * Self-service portal (thin, per M2): suppliers manage their company and
 * follow their verification case; buyers get their account surface (RFQ
 * intake arrives with M3).
 */
export default async function Portal({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const actor = await currentActor();
  if (!actor) redirect(`/${locale}/signin`);
  if (hasRole(actor, "ops")) redirect(`/${locale}/admin`);

  const session = await auth();
  const t = await getTranslations("portal");
  const common = await getTranslations("common");
  const tState = await getTranslations("caseState");
  const tItem = await getTranslations("itemStatus");
  const tCompanies = await getTranslations("companies");

  const isSupplier = actor.role === "supplier";
  const company = isSupplier ? await getCompanyByOwner(actor.userId) : null;

  const kase = company
    ? await db.query.verificationCases.findFirst({
        where: eq(verificationCases.companyId, company.id),
      })
    : null;

  const items = kase
    ? await db
        .select()
        .from(verificationItems)
        .where(and(eq(verificationItems.caseId, kase.id)))
    : [];

  const reqIds = [...new Set(items.map((i) => i.requirementDefinitionId))];
  const reqs = reqIds.length
    ? await db
        .select()
        .from(requirementDefinitions)
        .where(inArray(requirementDefinitions.id, reqIds))
    : [];
  const reqById = new Map(reqs.map((r) => [r.id, r]));
  const reqNameKey =
    locale === "sv" ? "nameSv" : locale === "lt" ? "nameLt" : "nameEn";

  const workers = company ? await listWorkers(company.id) : [];
  const state = kase?.state as CaseState | undefined;
  const capacity = company ? await listCompanyCapacity(company.id, false) : [];
  const trades = company ? await listTrades() : [];
  const primarySlug = company ? await getPrimarySlug(company.id) : null;
  const tradeNameKey =
    locale === "sv" ? "nameSv" : locale === "lt" ? "nameLt" : "nameEn";

  return (
    <div className="main" style={{ margin: "0 auto" }}>
      <div className="topbar">
        <Link href={`/${locale}`} className="brand" style={{ fontWeight: 800 }}>
          Baltic<strong>Bridge</strong>
        </Link>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
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
      </div>

      <h1>{t("title")}</h1>

      {/* Buyer surface */}
      {!isSupplier && (
        <div className="card mt">
          <h3>{t("buyerWelcome")}</h3>
          <p className="muted">{t("buyerBody")}</p>
        </div>
      )}

      {/* Supplier without a company yet: create it */}
      {isSupplier && !company && (
        <div className="card mt">
          <h3>{t("createCompanyTitle")}</h3>
          <p className="muted">{t("createCompanyBody")}</p>
          <form
            action={createMyCompanyAction}
            style={{ display: "grid", gap: "0.75rem", maxWidth: 480 }}
            className="mt"
          >
            <div>
              <label htmlFor="name">{tCompanies("name")}</label>
              <input id="name" name="name" required minLength={2} style={{ width: "100%" }} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "0.5rem" }}>
              <div>
                <label htmlFor="country">{tCompanies("country")}</label>
                <input id="country" name="country" required maxLength={2} defaultValue="LT" />
              </div>
              <div>
                <label htmlFor="city">{tCompanies("city")}</label>
                <input id="city" name="city" style={{ width: "100%" }} />
              </div>
            </div>
            <div>
              <label htmlFor="registrationNumber">{tCompanies("registrationNumber")}</label>
              <input id="registrationNumber" name="registrationNumber" style={{ width: "100%" }} />
            </div>
            <div>
              <label htmlFor="vatNumber">{tCompanies("vatNumber")}</label>
              <input id="vatNumber" name="vatNumber" style={{ width: "100%" }} />
            </div>
            <div>
              <label htmlFor="description">{t("companyDescription")}</label>
              <textarea id="description" name="description" rows={3} style={{ width: "100%" }} />
            </div>
            <button type="submit">{t("createCompanyCta")}</button>
          </form>
        </div>
      )}

      {/* Supplier with a company */}
      {isSupplier && company && (
        <>
          <div className="card mt">
            <h3>{company.name}</h3>
            <p className="muted">
              {company.country}
              {company.city ? ` · ${company.city}` : ""}
              {company.vatNumber ? ` · ${tCompanies("vatNumber")}: ${company.vatNumber}` : ""}
            </p>
            <p>
              {state ? (
                <>
                  <span className={`badge ${state}`}>{tState(state)}</span>{" "}
                  {badgeVisible(state) && (
                    <span className="badge verified">✓ {t("verifiedBadge")}</span>
                  )}
                </>
              ) : (
                <span className="muted">{t("awaitingCase")}</span>
              )}
              {primarySlug && (
                <>
                  {" · "}
                  <Link href={`/${locale}/company/${primarySlug}`}>
                    {t("publicProfileLink")}
                  </Link>
                </>
              )}
            </p>
          </div>

          {items.length > 0 && (
            <div className="card">
              <h3>{t("requirements")}</h3>
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                {t("requirementsHint")}
              </p>
              <table>
                <tbody>
                  {items.map((item) => {
                    const req = reqById.get(item.requirementDefinitionId);
                    const needsEvidence = ["missing", "rejected", "expired"].includes(
                      item.status,
                    );
                    return (
                      <tr key={item.id}>
                        <td>{req ? req[reqNameKey as never] : "—"}</td>
                        <td>
                          <span className={`badge ${item.status}`}>
                            {tItem(item.status)}
                          </span>
                        </td>
                        <td className="muted">
                          {item.validUntil
                            ? new Date(item.validUntil).toISOString().slice(0, 10)
                            : ""}
                        </td>
                        <td>
                          {needsEvidence && (
                            <UploadEvidence
                              itemId={item.id}
                              documentType={req?.key ?? "evidence"}
                            />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Profile editing — the Alibaba-style storefront data */}
          <div className="card">
            <h3>{t("editProfileTitle")}</h3>
            <form
              action={updateMyProfileAction}
              style={{ display: "grid", gap: "0.75rem", maxWidth: 520 }}
            >
              <div>
                <label htmlFor="p-description">{t("companyDescription")}</label>
                <textarea
                  id="p-description"
                  name="description"
                  rows={4}
                  defaultValue={company.description ?? ""}
                  style={{ width: "100%" }}
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                <div>
                  <label htmlFor="p-city">{tCompanies("city")}</label>
                  <input id="p-city" name="city" defaultValue={company.city ?? ""} />
                </div>
                <div>
                  <label htmlFor="p-website">{t("website")}</label>
                  <input id="p-website" name="website" defaultValue={company.website ?? ""} />
                </div>
                <div>
                  <label htmlFor="p-year">{t("yearFounded")}</label>
                  <input
                    id="p-year"
                    name="yearFounded"
                    type="number"
                    min={1900}
                    max={2100}
                    defaultValue={company.yearFounded ?? ""}
                  />
                </div>
                <div>
                  <label htmlFor="p-headcount">{t("headcount")}</label>
                  <input
                    id="p-headcount"
                    name="headcount"
                    type="number"
                    min={1}
                    defaultValue={company.headcount ?? ""}
                  />
                </div>
              </div>
              <div>
                <label>{t("languagesLabel")}</label>
                <div style={{ display: "flex", gap: "0.7rem", flexWrap: "wrap" }}>
                  {LANGUAGE_OPTIONS.map((lang) => (
                    <label
                      key={lang}
                      style={{ display: "inline-flex", gap: "0.25rem", alignItems: "center", margin: 0 }}
                    >
                      <input
                        type="checkbox"
                        name="languages"
                        value={lang}
                        defaultChecked={company.languages.includes(lang)}
                      />
                      {lang.toUpperCase()}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <button type="submit">{common("save")}</button>
              </div>
            </form>
          </div>

          {/* Capacity listings — "our teams are available" */}
          <div className="card">
            <h3>{t("capacityTitle")}</h3>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              {t("capacityHint")}
            </p>
            {capacity.length > 0 && (
              <table>
                <tbody>
                  {capacity.map((listing) => {
                    const trade = trades.find((tr) => tr.id === listing.tradeId);
                    return (
                      <tr key={listing.id}>
                        <td>
                          <strong>{trade ? trade[tradeNameKey as "nameEn"] : "—"}</strong>
                          {" · "}
                          {listing.headcount} {t("capacityWorkers")}
                        </td>
                        <td className="muted">
                          {listing.earliestStart
                            ? new Date(listing.earliestStart).toISOString().slice(0, 10)
                            : ""}
                          {listing.weeksAvailable ? ` · ${listing.weeksAvailable} v` : ""}
                        </td>
                        <td>
                          <span className={`badge ${listing.status === "published" ? "approved" : ""}`}>
                            {listing.status}
                          </span>
                        </td>
                        <td>
                          {listing.status !== "archived" && (
                            <form action={archiveMyCapacityAction}>
                              <input type="hidden" name="listingId" value={listing.id} />
                              <button type="submit" className="secondary">
                                {t("capacityArchive")}
                              </button>
                            </form>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
            <form action={createMyCapacityAction} className="inline mt">
              <div>
                <label htmlFor="c-trade">{t("capacityTrade")}</label>
                <select id="c-trade" name="tradeId" required>
                  {trades.map((trade) => (
                    <option key={trade.id} value={trade.id}>
                      {trade[tradeNameKey as "nameEn"]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="c-headcount">{t("capacityWorkers")}</label>
                <input id="c-headcount" name="headcount" type="number" min={1} required style={{ width: 80 }} />
              </div>
              <div>
                <label htmlFor="c-start">{t("capacityStart")}</label>
                <input id="c-start" name="earliestStart" type="date" />
              </div>
              <div>
                <label htmlFor="c-weeks">{t("capacityWeeks")}</label>
                <input id="c-weeks" name="weeksAvailable" type="number" min={1} style={{ width: 70 }} />
              </div>
              <div>
                <label htmlFor="c-certs">{t("capacityCerts")}</label>
                <input id="c-certs" name="certificationsSummary" placeholder="ISO 9606-1: 135, 136…" />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", paddingBottom: "0.4rem" }}>
                <input type="checkbox" id="c-publish" name="publish" defaultChecked />
                <label htmlFor="c-publish" style={{ margin: 0 }}>{t("capacityPublish")}</label>
              </div>
              <button type="submit">{common("create")}</button>
            </form>
          </div>

          <div className="card">
            <h3>{tCompanies("workers")}</h3>
            {workers.length > 0 && (
              <table>
                <tbody>
                  {workers.map((w) => (
                    <tr key={w.id}>
                      <td>{w.name}</td>
                      <td className="muted">{w.tradeRole ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <form action={addMyWorkerAction} className="inline mt">
              <input type="hidden" name="companyId" value={company.id} />
              <div>
                <label htmlFor="worker-name">{tCompanies("workerName")}</label>
                <input id="worker-name" name="name" required />
              </div>
              <div>
                <label htmlFor="worker-role">{tCompanies("tradeRole")}</label>
                <input id="worker-role" name="tradeRole" placeholder="welder" />
              </div>
              <button type="submit">{tCompanies("addWorker")}</button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
