import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const STORSTOCKHOLM = [
  "Stockholm", "Solna", "Sundbyberg", "Täby", "Danderyd", "Lidingö",
  "Nacka", "Sollentuna", "Järfälla", "Upplands Väsby", "Huddinge",
  "Botkyrka", "Haninge", "Tyresö", "Nynäshamn", "Vallentuna", "Vaxholm",
  "Österåker", "Ekerö", "Salem", "Nykvarn", "Södertälje",
];

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY is not configured");

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [
          {
            role: "system",
            content: `Du är B2B-säljare för Lennart Svenssons Konditorivaror, ett bageri i Stockholm som levererar färska handgjorda kakor på abonnemang till företag.

Din uppgift: identifiera potentiella B2B-kunder i STORSTOCKHOLM.

ABSOLUTA REGLER:
- Endast företag inom följande kommuner räknas som Storstockholm:
${STORSTOCKHOLM.map((k) => `  • ${k}`).join("\n")}
- Företag utanför Storstockholm får ALDRIG genereras.
- Använd endast verifierbar, realistisk information. Hitta inte på fakta.
- Fokusera på kontor 10+ anställda, hotell, restauranger, coworking, eventlokaler, större företag med personalrum/fika.
- Variera bransch och kommun – inte bara innerstaden.`,
          },
          {
            role: "user",
            content: "Generera 15 potentiella B2B-kunder för kakabonnemang i Storstockholm.",
          },
        ],
        tools: [
          {
            type: "function",
            function: {
              name: "generate_leads",
              description: "Returnerar en lista med potentiella B2B-kunder i Storstockholm",
              parameters: {
                type: "object",
                properties: {
                  leads: {
                    type: "array",
                    items: {
                      type: "object",
                      properties: {
                        company_name: { type: "string" },
                        industry: { type: "string" },
                        employee_count: { type: "number" },
                        district: {
                          type: "string",
                          description: "Kommun i Storstockholm (t.ex. Solna, Nacka, Södertälje)",
                        },
                        reason: { type: "string" },
                      },
                      required: ["company_name", "industry", "employee_count", "district", "reason"],
                      additionalProperties: false,
                    },
                  },
                },
                required: ["leads"],
                additionalProperties: false,
              },
            },
          },
        ],
        tool_choice: { type: "function", function: { name: "generate_leads" } },
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(JSON.stringify({ error: "Rate limit överskriden, försök igen senare." }), {
          status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      if (response.status === 402) {
        return new Response(JSON.stringify({ error: "Krediter slut, vänligen fyll på." }), {
          status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const errorText = await response.text();
      console.error("AI gateway error:", response.status, errorText);
      throw new Error(`AI gateway error: ${response.status}`);
    }

    const data = await response.json();
    const toolCall = data.choices?.[0]?.message?.tool_calls?.[0];
    if (!toolCall || toolCall.function.name !== "generate_leads") {
      throw new Error("Unexpected AI response format");
    }
    const parsed = JSON.parse(toolCall.function.arguments);

    // Extra säkerhet: filtrera bort allt utanför Storstockholm
    const allowed = new Set(STORSTOCKHOLM.map((s) => s.toLowerCase()));
    const leads = (parsed.leads || []).filter((l: any) =>
      allowed.has(String(l.district || "").toLowerCase().trim()),
    );

    return new Response(JSON.stringify({ leads }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Error generating leads:", error);
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
