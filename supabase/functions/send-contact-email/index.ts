import { serve } from "https://deno.land/std@0.190.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

interface ContactRequest {
  name: string;
  email: string;
  company: string;
  message: string;
}

// HTML-escape any user-supplied string before embedding in email HTML
const esc = (s: string): string =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

// In-memory rate limit per client IP (best-effort; resets on cold start).
// Key: ip, Value: array of request timestamps (ms).
const rateBuckets = new Map<string, number[]>();
const RATE_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const RATE_MAX = 5; // max 5 messages/hour per IP

function getClientIp(req: Request): string {
  const fwd = req.headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0].trim();
  return req.headers.get("cf-connecting-ip") || req.headers.get("x-real-ip") || "unknown";
}

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const bucket = (rateBuckets.get(ip) || []).filter((t) => now - t < RATE_WINDOW_MS);
  if (bucket.length >= RATE_MAX) {
    rateBuckets.set(ip, bucket);
    return false;
  }
  bucket.push(now);
  rateBuckets.set(ip, bucket);
  return true;
}

const handler = async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json", ...corsHeaders },
    });
  }

  const ip = getClientIp(req);
  if (!checkRateLimit(ip)) {
    return new Response(
      JSON.stringify({ error: "För många förfrågningar. Försök igen senare." }),
      {
        status: 429,
        headers: { "Content-Type": "application/json", ...corsHeaders },
      },
    );
  }

  try {
    const { name, email, company, message }: ContactRequest = await req.json();

    // Validate required fields
    if (!name || !email || !message) {
      throw new Error("Missing required fields");
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      throw new Error("Invalid email format");
    }

    // Validate field lengths
    if (
      name.length > 100 ||
      email.length > 255 ||
      (company && company.length > 100) ||
      message.length > 2000
    ) {
      throw new Error("Field length exceeded");
    }

    const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY");
    const recipientEmail = Deno.env.get("CONTACT_EMAIL") || "kontakt@example.com";

    if (!RESEND_API_KEY) {
      throw new Error("RESEND_API_KEY not configured");
    }

    // Escape all user-supplied values before embedding in HTML
    const safeName = esc(name);
    const safeEmail = esc(email);
    const safeCompany = company ? esc(company) : "";
    const safeMessage = esc(message).replace(/\n/g, "<br />");

    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${RESEND_API_KEY}`,
      },
      body: JSON.stringify({
        from: "Lennart Svensson Konditorivaror <noreply@lennartsvensson.se>",
        to: [recipientEmail],
        reply_to: email,
        subject: `Kontaktförfrågan från ${safeName}`,
        html: `
          <h2>Ny kontaktförfrågan</h2>
          <p><strong>Namn:</strong> ${safeName}</p>
          <p><strong>E-post:</strong> ${safeEmail}</p>
          ${safeCompany ? `<p><strong>Företag:</strong> ${safeCompany}</p>` : ""}
          <hr />
          <p><strong>Meddelande:</strong></p>
          <p>${safeMessage}</p>
        `,
      }),
    });

    if (!res.ok) {
      const error = await res.text();
      console.error("Resend API error:", error);
      throw new Error("Failed to send email");
    }

    const data = await res.json();
    console.log("Contact email sent successfully:", data);

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { "Content-Type": "application/json", ...corsHeaders },
    });
  } catch (error: any) {
    console.error("Error in send-contact-email function:", error);
    return new Response(
      JSON.stringify({ error: "Kunde inte skicka meddelandet." }),
      {
        status: 500,
        headers: { "Content-Type": "application/json", ...corsHeaders },
      },
    );
  }
};

serve(handler);
