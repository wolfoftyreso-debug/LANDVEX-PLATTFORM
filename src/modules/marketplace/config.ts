// Vertical UI configuration.
// The marketplace engine is generic — each vertical contributes its own
// presentation and RFQ metadata schema here. Categories live in the database.
import { HardHat, Car, Croissant, Factory, type LucideIcon } from "lucide-react";

export interface MetadataField {
  key: string;
  label: string;
  type: "text" | "textarea" | "date" | "select";
  options?: { value: string; label: string }[];
  placeholder?: string;
  required?: boolean;
}

export interface VerticalUiConfig {
  slug: string;
  label: string;
  tagline: string;
  icon: LucideIcon;
  rfqTitlePlaceholder: string;
  /** Schema version written to rfqs.metadata_schema_version */
  metadataSchemaVersion: number;
  metadataFields: MetadataField[];
}

export const VERTICALS: VerticalUiConfig[] = [
  {
    slug: "construction",
    label: "Construction",
    tagline:
      "Renovations, roofing, plumbing, electrical and more — from verified construction companies across Europe.",
    icon: HardHat,
    rfqTitlePlaceholder: "e.g. Full bathroom renovation, 8 m²",
    metadataSchemaVersion: 1,
    metadataFields: [
      {
        key: "property_type",
        label: "Property type",
        type: "select",
        options: [
          { value: "apartment", label: "Apartment" },
          { value: "house", label: "House" },
          { value: "commercial", label: "Commercial property" },
          { value: "other", label: "Other" },
        ],
        required: true,
      },
      {
        key: "size_sqm",
        label: "Approximate size (m²)",
        type: "text",
        placeholder: "e.g. 45",
      },
    ],
  },
  {
    slug: "automotive",
    label: "Automotive",
    tagline:
      "Body, paint and mechanical work — get quotes from verified workshops, with transport if you need it.",
    icon: Car,
    rfqTitlePlaceholder: "e.g. Front bumper respray, VW Golf 2019",
    metadataSchemaVersion: 1,
    metadataFields: [
      {
        key: "registration_number",
        label: "Registration number",
        type: "text",
        placeholder: "e.g. ABC123",
        required: true,
      },
      {
        key: "vin",
        label: "VIN (optional)",
        type: "text",
        placeholder: "17-character vehicle identification number",
      },
      {
        key: "damage_description",
        label: "Damage description",
        type: "textarea",
        placeholder: "Describe the damage or work needed",
      },
      {
        key: "insurance_company",
        label: "Insurance company (optional)",
        type: "text",
        placeholder: "If this is an insurance case",
      },
      {
        key: "desired_completion_date",
        label: "Desired completion date",
        type: "date",
      },
    ],
  },
  {
    slug: "food-production",
    label: "Bakery & Food",
    tagline:
      "Order from verified bakeries, confectioneries and food producers — one-off, recurring or wholesale.",
    icon: Croissant,
    rfqTitlePlaceholder: "e.g. 200 cinnamon buns weekly for our café",
    metadataSchemaVersion: 1,
    metadataFields: [
      {
        key: "order_type",
        label: "Order type",
        type: "select",
        options: [
          { value: "one_off", label: "One-off order" },
          { value: "recurring", label: "Recurring delivery" },
          { value: "wholesale", label: "Wholesale / B2B" },
          { value: "private_label", label: "Private label production" },
        ],
        required: true,
      },
      {
        key: "quantity",
        label: "Quantity / volume",
        type: "text",
        placeholder: "e.g. 200 pcs per week, 50 kg per month",
        required: true,
      },
      {
        key: "delivery_date",
        label: "First delivery date",
        type: "date",
      },
      {
        key: "dietary_requirements",
        label: "Allergens & dietary requirements",
        type: "textarea",
        placeholder: "e.g. gluten-free, nut-free facility, vegan, halal…",
      },
    ],
  },
  {
    slug: "manufacturing",
    label: "Manufacturing",
    tagline:
      "Custom production from verified workshops and factories — prototypes to serial manufacturing.",
    icon: Factory,
    rfqTitlePlaceholder: "e.g. 500 anodized aluminium brackets, CNC milled",
    metadataSchemaVersion: 1,
    metadataFields: [
      {
        key: "quantity",
        label: "Quantity",
        type: "text",
        placeholder: "e.g. 1 prototype + 500 series",
        required: true,
      },
      {
        key: "material",
        label: "Material",
        type: "text",
        placeholder: "e.g. 6061 aluminium, oak, ABS, stainless 316",
      },
      {
        key: "drawings_available",
        label: "Technical drawings available?",
        type: "select",
        options: [
          { value: "cad", label: "Yes — CAD files" },
          { value: "pdf", label: "Yes — PDF drawings" },
          { value: "sketch", label: "Only sketches / photos" },
          { value: "none", label: "No — need design help" },
        ],
      },
      {
        key: "tolerances",
        label: "Tolerances & specifications",
        type: "textarea",
        placeholder: "Critical dimensions, finish, standards (ISO/EN)…",
      },
      {
        key: "delivery_date",
        label: "Required delivery date",
        type: "date",
      },
    ],
  },
];

export function verticalConfig(slug: string): VerticalUiConfig | undefined {
  return VERTICALS.find((v) => v.slug === slug);
}
