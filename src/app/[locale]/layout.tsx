import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import "../globals.css";
import type { ReactNode } from "react";

const BASE_URL = process.env.PUBLIC_BASE_URL ?? "https://balticbridge.example";

export const metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "Baltic Bridge — verified cross-border subcontracting",
    template: "%s | Baltic Bridge",
  },
  description:
    "Verified cross-border subcontracting — Lithuania to Sweden. Compliance proven with documents and an audit trail.",
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!(routing.locales as readonly string[]).includes(locale)) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
