import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";
import { corsHeaders } from "npm:@supabase/supabase-js@2/cors";
import { z } from "https://esm.sh/zod@3.23.8";

const BodySchema = z.object({
  företag: z.string().trim().min(1).max(100),
  epost: z.string().trim().email().max(255),
  telefon: z.string().trim().max(30).optional().default(""),
  adress: z.string().trim().max(200).optional().default(""),
  postnummer: z
    .string()
    .trim()
    .regex(/^\s*\d{3}\s*\d{2}\s*$/, "Ogiltigt postnummer")
    .refine((v) => {
      const n = parseInt(v.replace(/\s/g, ""), 10);
      return n >= 10000 && n <= 19999;
    }, "Vi levererar endast inom Storstockholm (100 00 – 199 99)"),
  stad: z.string().trim().max(100).optional().default(""),
  kommentarer: z.string().trim().max(1000).optional().default(""),
  employees: z.number().int().min(1).max(1000),
  kg_per_vecka: z.number().min(1).max(500),
  pris_per_vecka: z.number().min(0).max(1000000),
});

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const parsed = BodySchema.safeParse(await req.json());
    if (!parsed.success) {
      return new Response(
        JSON.stringify({ error: parsed.error.flatten().fieldErrors }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }
    const d = parsed.data;

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const orderNumber = `ABO-${Date.now().toString(36).toUpperCase()}`;

    const { data, error } = await supabase
      .from("orders")
      .insert({
        order_number: orderNumber,
        customer_email: d.epost,
        customer_name: d.företag,
        items: [
          {
            typ: "Kakabonnemang",
            antal_anställda: d.employees,
            kg_per_vecka: d.kg_per_vecka,
            pris_per_vecka_exkl_moms: d.pris_per_vecka,
            valuta: "SEK",
            leverans: {
              adress: d.adress,
              postnummer: d.postnummer,
              stad: d.stad,
            },
            telefon: d.telefon,
            kommentarer: d.kommentarer,
          },
        ],
        total_amount: d.pris_per_vecka,
        currency: "SEK",
        status: "pending",
      })
      .select("id, order_number")
      .single();

    if (error) {
      console.error("Order insert failed:", error);
      return new Response(
        JSON.stringify({ error: "Kunde inte spara beställning", details: error.message }),
        {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    return new Response(JSON.stringify({ ok: true, order: data }), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("submit-order error:", e);
    return new Response(JSON.stringify({ error: (e as Error).message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
