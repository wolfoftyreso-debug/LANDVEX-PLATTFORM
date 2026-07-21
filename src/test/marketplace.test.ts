import { describe, it, expect } from "vitest";
import { slugify } from "@/modules/companies/api";
import { formatMoney } from "@/modules/core/types";
import { countryName, languageName } from "@/modules/core/countries";
import { verticalConfig, VERTICALS } from "@/modules/marketplace/config";

describe("slugify", () => {
  it("creates URL-safe permanent slugs", () => {
    expect(slugify("BuildPro Estonia")).toBe("buildpro-estonia");
    expect(slugify("  Åke's Bygg & Måleri AB  ")).toBe("ake-s-bygg-maleri-ab");
    expect(slugify("Auto-Lack GmbH!")).toBe("auto-lack-gmbh");
  });

  it("caps slug length at 60 characters", () => {
    expect(slugify("a".repeat(100)).length).toBeLessThanOrEqual(60);
  });
});

describe("formatMoney", () => {
  it("formats amounts with currency", () => {
    expect(formatMoney(1500, "EUR")).toContain("1,500");
    expect(formatMoney(1500, "EUR")).toContain("€");
  });
});

describe("countries and languages", () => {
  it("resolves ISO codes to names", () => {
    expect(countryName("EE")).toBe("Estonia");
    expect(countryName("SE")).toBe("Sweden");
    expect(languageName("sv")).toBe("Swedish");
  });

  it("falls back to the code for unknown values", () => {
    expect(countryName("XX")).toBe("XX");
  });
});

describe("vertical configuration (generic marketplace engine)", () => {
  it("ships the Phase 1 verticals plus production verticals", () => {
    expect(VERTICALS.map((v) => v.slug)).toEqual([
      "construction",
      "automotive",
      "food-production",
      "manufacturing",
    ]);
  });

  it("automotive RFQs require a registration number", () => {
    const automotive = verticalConfig("automotive");
    const reg = automotive?.metadataFields.find(
      (f) => f.key === "registration_number",
    );
    expect(reg?.required).toBe(true);
  });

  it("food production RFQs require order type and quantity", () => {
    const food = verticalConfig("food-production");
    const required = food?.metadataFields
      .filter((f) => f.required)
      .map((f) => f.key);
    expect(required).toEqual(["order_type", "quantity"]);
  });

  it("manufacturing RFQs require a quantity", () => {
    const manufacturing = verticalConfig("manufacturing");
    const qty = manufacturing?.metadataFields.find((f) => f.key === "quantity");
    expect(qty?.required).toBe(true);
  });

  it("every vertical declares a metadata schema version", () => {
    for (const v of VERTICALS) {
      expect(v.metadataSchemaVersion).toBeGreaterThanOrEqual(1);
    }
  });
});
