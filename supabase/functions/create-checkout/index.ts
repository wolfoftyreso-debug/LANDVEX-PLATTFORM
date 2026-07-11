import { z } from "npm:zod@3.23.8";
import { type StripeEnv, createStripeClient } from "../_shared/stripe.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const PRICE_PER_KG_ORE = 32500; // 325 kr in öre
const WEEKS_PER_MONTH = 4;

const BodySchema = z.object({
  method: z.enum(["card", "invoice"]),
  employees: z.number().int().min(1).max(500),
  kg_per_week: z.number().min(1).max(200),
  company: z.string().trim().min(1).max(200),
  email: z.string().trim().email().max(255),
  phone: z.string().trim().max(30).optional().default(""),
  address: z.string().trim().max(200).optional().default(""),
  postal_code: z.string().trim().min(1).max(20),
  city: z.string().trim().max(100).optional().default(""),
  comments: z.string().trim().max(1000).optional().default(""),
  return_url: z.string().url(),
  environment: z.enum(["sandbox", "live"]),
});

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const raw = await req.json();
    const parsed = BodySchema.safeParse(raw);
    if (!parsed.success) {
      return new Response(
        JSON.stringify({ error: "Ogiltiga fält", details: parsed.error.flatten().fieldErrors }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    const b = parsed.data;

    // Stockholm postal enforcement
    const cleaned = b.postal_code.replace(/\s/g, "");
    if (!/^\d{5}$/.test(cleaned) || parseInt(cleaned, 10) < 10000 || parseInt(cleaned, 10) > 19999) {
      return new Response(
        JSON.stringify({ error: "Vi levererar endast inom Storstockholm (100 00 – 199 99)." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const env: StripeEnv = b.environment;
    const stripe = createStripeClient(env);

    // Monthly amount in öre = kg × 4 veckor × 325 kr
    const monthlyAmountOre = Math.round(b.kg_per_week * WEEKS_PER_MONTH * PRICE_PER_KG_ORE);

    // Resolve product via existing price lookup_key
    const prices = await stripe.prices.list({ lookup_keys: ["kakabonnemang_dynamic"], limit: 1 });
    if (!prices.data.length) {
      return new Response(JSON.stringify({ error: "Produkt inte konfigurerad" }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    const productId =
      typeof prices.data[0].product === "string"
        ? prices.data[0].product
        : prices.data[0].product.id;

    // Find or create customer
    const existing = await stripe.customers.list({ email: b.email, limit: 1 });
    const customer =
      existing.data[0] ??
      (await stripe.customers.create({
        email: b.email,
        name: b.company,
        phone: b.phone || undefined,
        address: b.address
          ? {
              line1: b.address,
              postal_code: cleaned,
              city: b.city || undefined,
              country: "SE",
            }
          : undefined,
        metadata: {
          company: b.company,
          employees: String(b.employees),
          kg_per_week: String(b.kg_per_week),
          comments: b.comments,
        },
      }));

    if (b.method === "card") {
      // Embedded Checkout with dynamic recurring price_data
      const session = await stripe.checkout.sessions.create({
        mode: "subscription",
        ui_mode: "embedded_page" as any,
        return_url: b.return_url,
        customer: customer.id,
        line_items: [
          {
            quantity: 1,
            price_data: {
              currency: "sek",
              product: productId,
              recurring: { interval: "month" },
              unit_amount: monthlyAmountOre,
            } as any,
          },
        ],
        automatic_tax: { enabled: true },
        customer_update: { address: "auto", name: "auto" },
        subscription_data: {
          description: `Kakabonnemang – ${b.kg_per_week} kg/vecka`,
          metadata: {
            company: b.company,
            kg_per_week: String(b.kg_per_week),
            employees: String(b.employees),
          },
        },
        metadata: {
          company: b.company,
          kg_per_week: String(b.kg_per_week),
        },
      } as any);

      return new Response(JSON.stringify({ clientSecret: session.client_secret }), {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Invoice method: create subscription with send_invoice
    const subscription = await stripe.subscriptions.create({
      customer: customer.id,
      collection_method: "send_invoice",
      days_until_due: 30,
      items: [
        {
          price_data: {
            currency: "sek",
            product: productId,
            recurring: { interval: "month" },
            unit_amount: monthlyAmountOre,
            tax_behavior: "exclusive",
          } as any,
          quantity: 1,
        },
      ],
      automatic_tax: { enabled: true },
      description: `Kakabonnemang – ${b.kg_per_week} kg/vecka`,
      metadata: {
        company: b.company,
        kg_per_week: String(b.kg_per_week),
        employees: String(b.employees),
      },
    } as any);

    return new Response(
      JSON.stringify({
        invoice: true,
        subscription_id: subscription.id,
        message: "Faktura skickas till din e-post inom kort.",
      }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err: any) {
    console.error("create-checkout error:", err);
    return new Response(
      JSON.stringify({ error: err?.message ?? "Något gick fel vid checkout" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
