import { z } from "npm:zod@3.23.8";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const GATEWAY_URL = "https://connector-gateway.lovable.dev/brevo";

const BodySchema = z.object({
  to_email: z.string().email(),
  to_name: z.string().min(1).max(200),
  subject: z.string().min(1).max(300),
  body: z.string().min(1).max(10000),
});

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    const BREVO_API_KEY = Deno.env.get("BREVO_API_KEY");
    if (!LOVABLE_API_KEY || !BREVO_API_KEY) {
      throw new Error("Email service not configured");
    }

    const parsed = BodySchema.safeParse(await req.json());
    if (!parsed.success) {
      return new Response(
        JSON.stringify({ error: "Ogiltiga fält", details: parsed.error.flatten().fieldErrors }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    const { to_email, to_name, subject, body } = parsed.data;

    const senderEmail = Deno.env.get("BREVO_SENDER_EMAIL") ?? "konditorivaror@gmail.com";
    const senderName = "Tiffany – Lennart Svenssons Konditorivaror";

    // Konvertera radbrytningar till <br> för HTML
    const htmlBody = `
      <div style="font-family: Georgia, serif; font-size: 15px; color:#3d2817; line-height:1.6; max-width:600px;">
        ${body
          .split(/\n{2,}/)
          .map((p) => `<p>${p.replace(/\n/g, "<br/>")}</p>`)
          .join("")}
      </div>`;

    const res = await fetch(`${GATEWAY_URL}/v3/smtp/email`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "X-Connection-Api-Key": BREVO_API_KEY,
      },
      body: JSON.stringify({
        sender: { name: senderName, email: senderEmail },
        to: [{ email: to_email, name: to_name }],
        replyTo: { email: senderEmail, name: senderName },
        subject,
        htmlContent: htmlBody,
        textContent: body,
      }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      console.error(`Brevo send failed [${res.status}]:`, errBody);
      return new Response(
        JSON.stringify({ error: "Brevo avvisade mejlet", status: res.status, details: errBody }),
        { status: res.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const data = await res.json();
    return new Response(JSON.stringify({ success: true, messageId: data.messageId }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err: any) {
    console.error("send-outreach-email error:", err);
    return new Response(
      JSON.stringify({ error: err?.message ?? "Kunde inte skicka mejl" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
