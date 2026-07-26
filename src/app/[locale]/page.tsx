import { getTranslations, setRequestLocale } from "next-intl/server";
import Link from "next/link";
import SiteChrome from "@/app/[locale]/site-chrome";
import { localizedName } from "@/modules/catalog/i18n";
import { listTrades } from "@/modules/catalog/service";

export const dynamic = "force-dynamic";

/** Visual anchor per trade — decoration only, labels carry the meaning */
const TRADE_ICONS: Record<string, string> = {
  welding: "🔧",
  "industrial-fitting": "🏭",
  carpentry: "🪚",
  painting: "🎨",
  tiling: "🧱",
  roofing: "🏠",
  concrete: "🏗️",
  electrical: "⚡",
  "plumbing-hvac": "🚿",
  groundworks: "⛏️",
  "steel-structures": "🏢",
  demolition: "🔨",
  "property-services": "🧹",
};

export default async function Home({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  const tSup = await getTranslations("suppliers");
  const trades = await listTrades();

  return (
    <SiteChrome locale={locale}>
      <div className="search-hero">
        <h1>{t("tagline")}</h1>
        <p>{t("description")}</p>
        <form
          className="search-bar"
          method="get"
          action={`/${locale}/suppliers`}
        >
          <input
            name="q"
            placeholder={tSup("searchPlaceholder")}
            aria-label={tSup("searchLabel")}
          />
          <button type="submit">{tSup("searchCta")}</button>
        </form>
      </div>

      <div className="main" style={{ margin: "0 auto" }}>
        <h2 className="section-title">{t("categoriesTitle")}</h2>
        <div className="cat-grid">
          {trades.map((trade) => (
            <Link
              key={trade.id}
              className="cat-tile"
              href={`/${locale}/suppliers?q=${encodeURIComponent(trade.nameEn)}`}
            >
              <span className="icon" aria-hidden>
                {TRADE_ICONS[trade.slug] ?? "🛠️"}
              </span>
              <span className="label">{localizedName(trade, locale)}</span>
            </Link>
          ))}
        </div>

        <div className="trust-strip">✓ {t("trustLine")}</div>

        <h2 className="section-title">{t("howTitle")}</h2>
        <div className="steps">
          <div className="step">
            <span className="num">1</span>
            <h3>{t("how1t")}</h3>
            <p>{t("how1d")}</p>
          </div>
          <div className="step">
            <span className="num">2</span>
            <h3>{t("how2t")}</h3>
            <p>{t("how2d")}</p>
          </div>
          <div className="step">
            <span className="num">3</span>
            <h3>{t("how3t")}</h3>
            <p>{t("how3d")}</p>
          </div>
        </div>

        <p
          className="mt"
          style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}
        >
          <Link className="button" href={`/${locale}/request-work`}>
            {t("requestWorkCta")}
          </Link>
          <Link
            className="button"
            href={`/${locale}/register`}
            style={{ background: "var(--surface)", color: "var(--primary)" }}
          >
            {t("joinAsSupplier")}
          </Link>
        </p>
      </div>
    </SiteChrome>
  );
}
