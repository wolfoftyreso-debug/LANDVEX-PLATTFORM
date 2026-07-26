import { notFound, permanentRedirect } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import {
  listCompanyCapacity,
  listPortfolio,
  listReferences,
  resolveCompanySlug,
} from "@/modules/companies/service";
import { presignGet } from "@/modules/documents/service";
import { getCorridorBySlug, listTrades } from "@/modules/catalog/service";
import { getVerifiedFacts } from "@/modules/verification/service";
import { getCompanyByOwner } from "@/modules/companies/service";
import { currentActor } from "@/lib/auth";
import { routing } from "@/i18n/routing";
import SiteChrome from "@/app/[locale]/site-chrome";
import Link from "next/link";
import { requestClaimAction } from "./claim-actions";

export const dynamic = "force-dynamic";

const BASE_URL = process.env.PUBLIC_BASE_URL ?? "https://balticbridge.example";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}): Promise<Metadata> {
  const { locale, slug } = await params;
  const resolved = await resolveCompanySlug(slug);
  if (!resolved) return {};
  const { company, primarySlug } = resolved;

  const languages = Object.fromEntries(
    routing.locales.map((l) => [l, `${BASE_URL}/${l}/company/${primarySlug}`]),
  );

  return {
    title: `${company.name} — Baltic Bridge`,
    description:
      company.description?.slice(0, 160) ??
      `${company.name} on Baltic Bridge — the verified cross-border subcontracting marketplace.`,
    alternates: {
      canonical: `${BASE_URL}/${locale}/company/${primarySlug}`,
      languages,
    },
    openGraph: {
      title: company.name,
      description: company.description?.slice(0, 200) ?? undefined,
      type: "profile",
    },
  };
}

/** Public verified company profile at a permanent URL (M2) */
export default async function PublicCompanyPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  const resolved = await resolveCompanySlug(slug);
  if (!resolved) notFound();
  // Renamed companies keep old URLs working via permanent redirects
  if (!resolved.isPrimary) {
    permanentRedirect(`/${locale}/company/${resolved.primarySlug}`);
  }
  const { company } = resolved;

  const t = await getTranslations("publicProfile");
  const corridor = await getCorridorBySlug("lt-se");
  const verifiedFacts = corridor
    ? await getVerifiedFacts(company.id, corridor.id)
    : { verified: false, verifiedSince: null, facts: [] };

  const [capacity, trades, approvedPortfolio, references] = await Promise.all([
    listCompanyCapacity(company.id, true),
    listTrades(),
    listPortfolio(company.id, { onlyApproved: true }),
    listReferences(company.id),
  ]);
  // Signed URLs ≤ 15 min (Section 4.7); generated per request, best effort
  const portfolioImages = await Promise.all(
    approvedPortfolio.map(async (item) => ({
      ...item,
      url: await presignGet(item.objectKey).catch(() => null),
    })),
  );

  // Claim eligibility: signed-in supplier without a company of their own
  const actor = await currentActor();
  const canClaim =
    company.claimStatus === "unclaimed" &&
    actor?.role === "supplier" &&
    !(await getCompanyByOwner(actor.userId));
  const tradeById = new Map(trades.map((tr) => [tr.id, tr]));
  const tradeNameKey =
    locale === "sv" ? "nameSv" : locale === "lt" ? "nameLt" : "nameEn";
  const factNameKey =
    locale === "sv" ? "nameSv" : locale === "lt" ? "nameLt" : "nameEn";

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: company.name,
    url: `${BASE_URL}/${locale}/company/${slug}`,
    address: {
      "@type": "PostalAddress",
      addressLocality: company.city ?? undefined,
      addressCountry: company.country,
    },
    foundingDate: company.yearFounded ? String(company.yearFounded) : undefined,
    numberOfEmployees: company.headcount ?? undefined,
    vatID: company.vatNumber ?? undefined,
  };

  return (
    <SiteChrome locale={locale}>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="main" style={{ margin: "0 auto" }}>
        <h1>{company.name}</h1>
        <p className="muted">
          {company.city ? `${company.city}, ` : ""}
          {company.country}
          {company.yearFounded ? ` · ${t("founded")} ${company.yearFounded}` : ""}
          {company.headcount ? ` · ${company.headcount} ${t("employees")}` : ""}
          {company.languages.length > 0
            ? ` · ${t("languages")}: ${company.languages.join(", ").toUpperCase()}`
            : ""}
        </p>

        {/* Unclaimed catalog profile: provenance + takeover via verification */}
        {company.claimStatus === "unclaimed" && (
          <div className="card" style={{ borderColor: "var(--warning)" }}>
            <h3 style={{ marginTop: 0 }}>
              <span className="badge in_review">{t("unclaimedBadge")}</span>
            </h3>
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              {t("unclaimedBody")}
              {company.sourceUrl && (
                <>
                  {" "}
                  {t("sourceLabel")}:{" "}
                  <a href={company.sourceUrl} rel="nofollow noopener noreferrer" target="_blank">
                    {company.sourceName ?? company.sourceUrl}
                  </a>
                  .
                </>
              )}
            </p>
            {canClaim ? (
              <form action={requestClaimAction}>
                <input type="hidden" name="companyId" value={company.id} />
                <button type="submit" className="button" style={{ font: "inherit", fontWeight: 600, cursor: "pointer" }}>
                  {t("claimCta")}
                </button>
              </form>
            ) : (
              <Link className="button" href={`/${locale}/register`}>
                {t("claimRegisterCta")}
              </Link>
            )}
          </div>
        )}

        {company.description && (
          <div className="card">
            <p style={{ margin: 0, whiteSpace: "pre-line" }}>{company.description}</p>
            {(company.category || company.website) && (
              <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>
                {company.category}
                {company.website && (
                  <>
                    {company.category ? " · " : ""}
                    <a href={company.website} rel="nofollow noopener noreferrer" target="_blank">
                      {company.website.replace(/^https?:\/\//, "")}
                    </a>
                  </>
                )}
              </p>
            )}
          </div>
        )}

        {/* Service areas + self-reported certifications (kept clearly apart
            from the platform-VERIFIED facts panel below) */}
        {(company.serviceAreas.length > 0 || company.certifications.length > 0) && (
          <div className="card">
            {company.serviceAreas.length > 0 && (
              <p style={{ margin: 0 }}>
                <strong>{t("serviceAreas")}:</strong>{" "}
                {company.serviceAreas.join(" · ")}
              </p>
            )}
            {company.certifications.length > 0 && (
              <p className="muted" style={{ margin: company.serviceAreas.length ? "0.5rem 0 0" : 0, fontSize: "0.9rem" }}>
                <strong>{t("selfReportedCerts")}:</strong>{" "}
                {company.certifications.join(" · ")}{" "}
                <span style={{ fontSize: "0.8rem" }}>({t("selfReportedNote")})</span>
              </p>
            )}
          </div>
        )}

        {/* Verified panel — ONLY platform-verified facts, binary badge */}
        <div className="card" style={verifiedFacts.verified ? { borderColor: "var(--success)" } : undefined}>
          <h2 style={{ marginTop: 0 }}>
            {verifiedFacts.verified ? (
              <span className="badge verified" style={{ fontSize: "0.95rem" }}>
                ✓ {t("verifiedBadge")}
              </span>
            ) : (
              <span className="badge">{t("notVerified")}</span>
            )}
          </h2>
          {verifiedFacts.verified ? (
            <>
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                {t("verifiedExplainer")}
                {verifiedFacts.verifiedSince && (
                  <>
                    {" "}
                    {t("verifiedSince")}{" "}
                    {new Date(verifiedFacts.verifiedSince).toISOString().slice(0, 10)}.
                  </>
                )}
              </p>
              <table>
                <tbody>
                  {company.registrationNumber && (
                    <tr>
                      <td>{t("orgNumber")}</td>
                      <td><strong>{company.registrationNumber}</strong> ✓</td>
                    </tr>
                  )}
                  {verifiedFacts.facts.map((fact) => (
                    <tr key={fact.key}>
                      <td>{fact[factNameKey as "nameEn"]}</td>
                      <td>
                        <strong>✓</strong>
                        {fact.workerCount ? ` × ${fact.workerCount}` : ""}
                        {typeof fact.metadata.approval_date === "string" &&
                          ` · ${fact.metadata.approval_date}`}
                        {typeof fact.metadata.insurer === "string" &&
                          ` · ${fact.metadata.insurer}`}
                        {typeof fact.metadata.status === "string" &&
                          ` · ${fact.metadata.status}`}
                        {fact.validUntil &&
                          ` · ${t("validUntil")} ${new Date(fact.validUntil).toISOString().slice(0, 10)}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p className="muted" style={{ margin: 0 }}>{t("notVerifiedExplainer")}</p>
          )}
        </div>

        {/* Project images — only ops-approved items are shown */}
        {portfolioImages.length > 0 && (
          <div className="card">
            <h2 style={{ marginTop: 0 }}>{t("portfolioTitle")}</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: "0.75rem" }}>
              {portfolioImages.map((item) => (
                <figure key={item.id} style={{ margin: 0 }}>
                  {item.url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={item.url}
                      alt={item.title}
                      style={{ width: "100%", height: 150, objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)" }}
                    />
                  ) : (
                    <div style={{ height: 150, borderRadius: 8, border: "1px dashed var(--border)", display: "grid", placeItems: "center" }} className="muted">
                      {item.title}
                    </div>
                  )}
                  <figcaption className="muted" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                    {item.title}
                  </figcaption>
                </figure>
              ))}
            </div>
          </div>
        )}

        {/* References — collected and checked by Baltic Bridge ops */}
        {references.length > 0 && (
          <div className="card">
            <h2 style={{ marginTop: 0 }}>{t("referencesTitle")}</h2>
            <p className="muted" style={{ fontSize: "0.85rem" }}>{t("referencesNote")}</p>
            <div className="scroll">
              <table>
                <tbody>
                  {references.map((reference) => (
                    <tr key={reference.id}>
                      <td>
                        <strong>{reference.projectTitle}</strong>
                        {reference.scopeSummary && (
                          <div className="muted" style={{ fontSize: "0.85rem" }}>
                            {reference.scopeSummary}
                          </div>
                        )}
                      </td>
                      <td className="muted">
                        {reference.clientName} · {reference.country}
                        {reference.year ? ` · ${reference.year}` : ""}
                      </td>
                      <td className="muted" style={{ fontSize: "0.8rem" }}>
                        {t("referenceContact")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Capacity listings */}
        {capacity.length > 0 && (
          <div className="card">
            <h2 style={{ marginTop: 0 }}>{t("capacityTitle")}</h2>
            <table>
              <tbody>
                {capacity.map((listing) => {
                  const trade = tradeById.get(listing.tradeId);
                  return (
                    <tr key={listing.id}>
                      <td>
                        <strong>
                          {trade ? trade[tradeNameKey as "nameEn"] : "—"}
                        </strong>
                        {listing.certificationsSummary && (
                          <div className="muted" style={{ fontSize: "0.8rem" }}>
                            {listing.certificationsSummary}
                          </div>
                        )}
                      </td>
                      <td>{listing.headcount} {t("workers")}</td>
                      <td className="muted">
                        {listing.earliestStart
                          ? `${t("earliestStart")}: ${new Date(listing.earliestStart).toISOString().slice(0, 10)}`
                          : ""}
                        {listing.weeksAvailable
                          ? ` · ${listing.weeksAvailable} ${t("weeks")}`
                          : ""}
                        {listing.baseLocation ? ` · ${listing.baseLocation}` : ""}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="card" style={{ background: "var(--primary)", color: "#fff" }}>
          <h3 style={{ marginTop: 0 }}>{t("ctaTitle")}</h3>
          <p style={{ opacity: 0.9 }}>{t("ctaBody")}</p>
          <a
            className="button"
            style={{ background: "#fff", color: "var(--primary)" }}
            href={`mailto:ops@balticbridge.example?subject=${encodeURIComponent(
              `Work request via Baltic Bridge: ${company.name}`,
            )}`}
          >
            {t("ctaButton")}
          </a>
        </div>
      </div>
    </SiteChrome>
  );
}
