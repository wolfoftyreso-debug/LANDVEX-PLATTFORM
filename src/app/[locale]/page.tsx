import { getTranslations, setRequestLocale } from "next-intl/server";
import Link from "next/link";

export default async function Home({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  const common = await getTranslations("common");

  return (
    <div className="hero">
      <div className="inner">
        <h1>{common("appName")}</h1>
        <p>
          <strong>{t("tagline")}</strong>
        </p>
        <p>{t("description")}</p>
        <p className="mt" style={{ display: "flex", gap: "0.5rem", justifyContent: "center", flexWrap: "wrap" }}>
          <Link className="button" href={`/${locale}/register`}>
            {t("joinAsSupplier")}
          </Link>
          <Link className="button" href={`/${locale}/register`} style={{ background: "var(--surface)", color: "var(--primary)" }}>
            {t("joinAsBuyer")}
          </Link>
          <Link className="button" href={`/${locale}/suppliers`} style={{ background: "var(--surface)", color: "var(--primary)" }}>
            {t("findSuppliers")}
          </Link>
        </p>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          <Link href={`/${locale}/signin`}>{t("goToAdmin")}</Link>
        </p>
      </div>
    </div>
  );
}
