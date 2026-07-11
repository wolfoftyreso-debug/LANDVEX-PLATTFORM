import { z } from "npm:zod@3.23.8";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const GATEWAY_URL = "https://connector-gateway.lovable.dev/brevo";

const BodySchema = z.object({
  order_number: z.string().min(1).max(100),
  customer_email: z.string().email(),
  customer_name: z.string().min(1).max(200),
  kg_per_week: z.number().min(0),
  employees: z.number().int().min(0),
  monthly_amount_sek: z.number().min(0),
  method: z.enum(["card", "invoice"]),
  address: z.string().max(200).optional().default(""),
  postal_code: z.string().max(20).optional().default(""),
  phone: z.string().max(30).optional().default(""),
  comments: z.string().max(1000).optional().default(""),
});

function fmtKr(n: number) {
  return new Intl.NumberFormat("sv-SE", {
    style: "currency",
    currency: "SEK",
    maximumFractionDigits: 0,
  }).format(n);
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    const BREVO_API_KEY = Deno.env.get("BREVO_API_KEY");
    if (!LOVABLE_API_KEY || !BREVO_API_KEY) {
      throw new Error("Email service not configured");
    }

    const raw = await req.json();
    const parsed = BodySchema.safeParse(raw);
    if (!parsed.success) {
      return new Response(
        JSON.stringify({ error: "Ogiltiga fält", details: parsed.error.flatten().fieldErrors }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    const o = parsed.data;

    const senderEmail = Deno.env.get("BREVO_SENDER_EMAIL") ?? "noreply@konditorivaror.se";
    const senderName = Deno.env.get("BREVO_SENDER_NAME") ?? "Lennart Svensson Konditorivaror";
    const adminEmail = Deno.env.get("ORDER_NOTIFICATION_EMAIL") ?? senderEmail;

    const methodLabel = o.method === "card" ? "Kort (månadsvis)" : "Faktura (månadsvis)";

    const customerHtml = `
      <div style="font-family: Georgia, serif; color:#3d2817; max-width:600px; margin:0 auto; padding:24px;">
        <h1 style="color:#7a4a1f;">Tack för din beställning!</h1>
        <p>Hej ${o.customer_name},</p>
        <p>Vi har mottagit din beställning av <strong>Kakabonnemang</strong>. Goda saker är på väg – leverans varje tisdag inom Storstockholm.</p>
        <h2 style="color:#7a4a1f; margin-top:24px;">Orderdetaljer</h2>
        <table style="width:100%; border-collapse:collapse;">
          <tr><td style="padding:6px 0;"><strong>Ordernummer:</strong></td><td>${o.order_number}</td></tr>
          <tr><td style="padding:6px 0;"><strong>Mängd:</strong></td><td>${o.kg_per_week} kg/vecka</td></tr>
          <tr><td style="padding:6px 0;"><strong>Antal anställda:</strong></td><td>${o.employees}</td></tr>
          <tr><td style="padding:6px 0;"><strong>Månadskostnad (exkl. moms):</strong></td><td>${fmtKr(o.monthly_amount_sek)}</td></tr>
          <tr><td style="padding:6px 0;"><strong>Betalning:</strong></td><td>${methodLabel}</td></tr>
        </table>
        <p style="margin-top:24px;">Har du frågor? Svara bara på detta mejl.</p>
        <p style="color:#7a4a1f; font-style:italic;">Äkta svenskt konditorhantverk</p>
      </div>`;

    const adminHtml = `
      <div style="font-family: Arial, sans-serif; color:#111; max-width:600px;">
        <h2>Ny order: ${o.order_number}</h2>
        <p><strong>Företag:</strong> ${o.customer_name}<br/>
           <strong>E-post:</strong> ${o.customer_email}<br/>
           <strong>Telefon:</strong> ${o.phone || "-"}</p>
        <p><strong>Mängd:</strong> ${o.kg_per_week} kg/vecka<br/>
           <strong>Anställda:</strong> ${o.employees}<br/>
           <strong>Månadskostnad (exkl moms):</strong> ${fmtKr(o.monthly_amount_sek)}<br/>
           <strong>Betalning:</strong> ${methodLabel}</p>
        <p><strong>Leverans:</strong> ${o.address || "-"}, ${o.postal_code || "-"}</p>
        ${o.comments ? `<p><strong>Kommentar:</strong> ${o.comments}</p>` : ""}
      </div>`;

    async function send(to: string, subject: string, html: string) {
      const res = await fetch(`${GATEWAY_URL}/v3/smtp/email`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${LOVABLE_API_KEY}`,
          "X-Connection-Api-Key": BREVO_API_KEY,
        },
        body: JSON.stringify({
          sender: { name: senderName, email: senderEmail },
          to: [{ email: to }],
          subject,
          htmlContent: html,
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        console.error(`Brevo send failed [${res.status}]:`, body);
        throw new Error(`Brevo ${res.status}: ${body}`);
      }
      return res.json();
    }

    const results = await Promise.allSettled([
      send(o.customer_email, `Orderbekräftelse ${o.order_number} – Lennart Svensson Konditorivaror`, customerHtml),
      send(adminEmail, `Ny order: ${o.order_number} (${o.customer_name})`, adminHtml),
    ]);

    const errors = results
      .map((r, i) => (r.status === "rejected" ? { i, reason: String(r.reason) } : null))
      .filter(Boolean);

    return new Response(
      JSON.stringify({ success: errors.length === 0, errors }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err: any) {
    console.error("send-order-email error:", err);
    return new Response(
      JSON.stringify({ error: err?.message ?? "Kunde inte skicka mejl" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
