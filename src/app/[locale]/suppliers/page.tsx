import Link from "next/link";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { searchSuppliers } from "@/modules/search/service";
import SiteChrome from "@/app/[locale]/site-chrome";

export const dynamic = "force-dynamic";

/** Public supplier directory — Postgres FTS + trigram, verified first */
export default async function Suppliers({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string; country?: string; verified?: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("suppliers");
  const query = await searchParams;

  const hits = await searchSuppliers({
    q: query.q,
    country: query.country || undefined,
    verifiedOnly: query.verified === "1",
  });

  return (
    <SiteChrome locale={locale}>
      <div className="main" style={{ margin: "0 auto" }}>
        <h1>{t("title")}</h1>
        <p className="muted">{t("subtitle")}</p>

        <form method="get" className="inline card mt">
          <div style={{ flex: 1, minWidth: 220 }}>
            <label htmlFor="q">{t("searchLabel")}</label>
            <input
              id="q"
              name="q"
              defaultValue={query.q ?? ""}
              placeholder={t("searchPlaceholder")}
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <label htmlFor="country">{t("country")}</label>
            <select id="country" name="country" defaultValue={query.country ?? ""}>
              <option value="">{t("anyCountry")}</option>
              <option value="LT">Lietuva</option>
              <option value="LV">Latvija</option>
              <option value="EE">Eesti</option>
            </select>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", paddingBottom: "0.5rem" }}>
            <input
              type="checkbox"
              id="verified"
              name="verified"
              value="1"
              defaultChecked={query.verified === "1"}
            />
            <label htmlFor="verified" style={{ margin: 0 }}>{t("verifiedOnly")}</label>
          </div>
          <button type="submit">{t("searchCta")}</button>
        </form>

        {hits.length === 0 ? (
          <p className="muted mt">{t("empty")}</p>
        ) : (
          <div className="mt">
            {hits.map((hit) => (
              <div key={hit.companyId} className="card">
                <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
                  <div>
                    <h3 style={{ marginBottom: "0.15rem" }}>
                      {hit.slug ? (
                        <Link href={`/${locale}/company/${hit.slug}`}>{hit.name}</Link>
                      ) : (
                        hit.name
                      )}
                    </h3>
                    <div className="muted" style={{ fontSize: "0.85rem" }}>
                      {hit.country}
                      {hit.city ? ` · ${hit.city}` : ""}
                      {hit.yearFounded ? ` · ${t("since")} ${hit.yearFounded}` : ""}
                      {hit.headcount ? ` · ${hit.headcount} ${t("employees")}` : ""}
                    </div>
                    {hit.description && (
                      <p className="muted" style={{ fontSize: "0.9rem", marginBottom: 0 }}>
                        {hit.description.slice(0, 180)}
                        {hit.description.length > 180 ? "…" : ""}
                      </p>
                    )}
                  </div>
                  <div>
                    {hit.verified ? (
                      <span className="badge verified">✓ {t("verifiedBadge")}</span>
                    ) : (
                      <span className="badge">{t("notVerified")}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </SiteChrome>
  );
}
