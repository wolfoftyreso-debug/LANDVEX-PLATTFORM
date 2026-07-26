import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  // sv/en + every supplier-side language: Lithuanian, Latvian, Estonian, Polish
  locales: ["sv", "en", "lt", "lv", "et", "pl"],
  defaultLocale: "sv",
});
