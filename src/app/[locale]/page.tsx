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
        <p className="mt">
          <Link className="button" href={`/${locale}/admin`}>
            {t("goToAdmin")}
          </Link>
        </p>
      </div>
    </div>
  );
}
