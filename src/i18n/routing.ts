import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["sv", "en", "lt"],
  defaultLocale: "sv",
});
