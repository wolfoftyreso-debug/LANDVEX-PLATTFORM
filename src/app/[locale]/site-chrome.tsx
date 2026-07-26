import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { routing } from "@/i18n/routing";

const LOCALE_LABELS: Record<string, string> = {
  sv: "Svenska",
  en: "English",
  lt: "Lietuvių",
  lv: "Latviešu",
  et: "Eesti",
  pl: "Polski",
};

/** Public site header/footer (marketing + directory pages) */
export default async function SiteChrome({
  locale,
  children,
}: {
  locale: string;
  children: ReactNode;
}) {
  const t = await getTranslations("chrome");
  const common = await getTranslations("common");

  return (
    <div>
      <header
        style={{
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
        }}
      >
        <div
          className="main"
          style={{
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingTop: "0.9rem",
            paddingBottom: "0.9rem",
          }}
        >
          <Link href={`/${locale}`} style={{ fontWeight: 800, fontSize: "1.05rem" }}>
            Baltic<strong style={{ color: "var(--primary)" }}>Bridge</strong>
          </Link>
          <nav style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
            <Link href={`/${locale}/suppliers`}>{t("findSuppliers")}</Link>
            <Link href={`/${locale}/request-work`}>{t("requestWork")}</Link>
            <Link href={`/${locale}/register`}>{t("join")}</Link>
            <Link className="button" href={`/${locale}/signin`} style={{ padding: "0.3rem 0.8rem" }}>
              {common("signIn")}
            </Link>
          </nav>
        </div>
      </header>
      {children}
      <footer
        style={{
          borderTop: "1px solid var(--border)",
          marginTop: "3rem",
          padding: "1.5rem 0",
          textAlign: "center",
        }}
        className="muted"
      >
        <div style={{ marginBottom: "0.5rem" }}>
          <Link href={`/${locale}/markets/sweden`}>{t("marketSweden")}</Link>
          {" · "}
          <Link href={`/${locale}/markets/norway`}>{t("marketNorway")}</Link>
          {" · "}
          <Link href={`/${locale}/markets/denmark`}>{t("marketDenmark")}</Link>
        </div>
        <div style={{ marginBottom: "0.5rem", fontSize: "0.85rem" }}>
          {routing.locales.map((l, i) => (
            <span key={l}>
              {i > 0 && " · "}
              {l === locale ? (
                <strong>{LOCALE_LABELS[l] ?? l}</strong>
              ) : (
                <Link href={`/${l}`} lang={l} hrefLang={l}>
                  {LOCALE_LABELS[l] ?? l}
                </Link>
              )}
            </span>
          ))}
        </div>
        Baltic Bridge — {t("footerLine")}
      </footer>
    </div>
  );
}
