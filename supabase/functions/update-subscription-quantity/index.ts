import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";
import { z } from "npm:zod@3.23.8";
import { type StripeEnv, createStripeClient } from "../_shared/stripe.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, x-supabase-client-platform, x-supabase-api-version, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const PRICE_PER_KG_ORE = 32500; // 325 kr exkl. moms
const WEEKS_PER_MONTH = 4;

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const BodySchema = z.object({
  new_kg_per_week: z.number().min(1).max(200),
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
    const token = req.headers.get("Authorization")?.replace("Bearer ", "") ?? "";
    const { data: userData, error: authErr } = await supabase.auth.getUser(token);
    if (authErr || !userData?.user) {
      return new Response(JSON.stringify({ error: "Ej inloggad" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const parsed = BodySchema.safeParse(await req.json());
    if (!parsed.success) {
      return new Response(JSON.stringify({ error: "Ogiltiga fält" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const env: StripeEnv = parsed.data.environment;
    const newKg = parsed.data.new_kg_per_week;

    const { data: sub } = await supabase
      .from("subscriptions")
      .select("id, stripe_subscription_id, kg_per_week")
      .eq("user_id", userData.user.id)
      .eq("environment", env)
      .in("status", ["active", "trialing", "past_due"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (!sub?.stripe_subscription_id) {
      return new Response(
        JSON.stringify({ error: "Inget aktivt abonnemang hittades." }),
        { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const stripe = createStripeClient(env);
    const stripeSub = await stripe.subscriptions.retrieve(sub.stripe_subscription_id);
    const item = stripeSub.items?.data?.[0];
    if (!item) {
      return new Response(JSON.stringify({ error: "Kunde inte hitta prisrad" }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const productId =
      typeof item.price.product === "string" ? item.price.product : item.price.product.id;
    const newUnitAmount = Math.round(newKg * WEEKS_PER_MONTH * PRICE_PER_KG_ORE);

    await stripe.subscriptions.update(sub.stripe_subscription_id, {
      items: [
        {
          id: item.id,
          price_data: {
            currency: "sek",
            product: productId,
            recurring: { interval: "month" },
            unit_amount: newUnitAmount,
          } as any,
          quantity: 1,
        },
      ],
      proration_behavior: "create_prorations",
      metadata: {
        ...(stripeSub.metadata ?? {}),
        kg_per_week: String(newKg),
      },
      description: `Kakabonnemang – ${newKg} kg/vecka`,
    } as any);

    // Uppdatera vår tabell direkt (webhook uppdaterar också, detta ger snabb UI-återkoppling)
    await supabase
      .from("subscriptions")
      .update({
        kg_per_week: newKg,
        monthly_amount: newUnitAmount / 100,
        updated_at: new Date().toISOString(),
      })
      .eq("id", sub.id);

    return new Response(
      JSON.stringify({
        success: true,
        new_kg_per_week: newKg,
        new_monthly_amount_exkl_moms: newUnitAmount / 100,
      }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (e: any) {
    console.error("update-subscription-quantity error:", e);
    return new Response(JSON.stringify({ error: e?.message ?? "Kunde inte uppdatera abonnemang" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
