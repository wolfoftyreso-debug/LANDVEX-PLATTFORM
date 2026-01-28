import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) {
      throw new Error("LOVABLE_API_KEY is not configured");
    }

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
            content: `Du är en B2B-säljexpert som identifierar potentiella kunder för ett bageri som levererar färska kakor till företag i Storstockholm. 
            
Generera en lista med 15 verkliga eller realistiska företag i Storstockholmsområdet som skulle vara bra kunder för veckovisa kakleveranser. 
Fokusera på:
- Kontor med 10+ anställda
- Hotell och restauranger
- Caféer och fik
- Eventlokaler
- Coworking-spaces
- Större företag med personalrum/fika

För varje företag, ange:
- Företagsnamn
- Bransch
- Uppskattat antal anställda
- Stadsdel i Stockholm
- Varför de är en bra kund (kort)`
          },
          {
            role: "user",
            content: "Generera 15 potentiella B2B-kunder för kakleveranser i Storstockholm."
          }
        ],
        tools: [
          {
            type: "function",
            function: {
              name: "generate_leads",
              description: "Returnerar en lista med potentiella B2B-kunder",
              parameters: {
                type: "object",
                properties: {
                  leads: {
                    type: "array",
                    items: {
                      type: "object",
                      properties: {
                        company_name: { type: "string", description: "Företagets namn" },
                        industry: { type: "string", description: "Bransch" },
                        employee_count: { type: "number", description: "Antal anställda" },
                        district: { type: "string", description: "Stadsdel i Stockholm" },
                        reason: { type: "string", description: "Varför de är en bra kund" }
                      },
                      required: ["company_name", "industry", "employee_count", "district", "reason"],
                      additionalProperties: false
                    }
                  }
                },
                required: ["leads"],
                additionalProperties: false
              }
            }
          }
        ],
        tool_choice: { type: "function", function: { name: "generate_leads" } }
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(JSON.stringify({ error: "Rate limit överskriden, försök igen senare." }), {
          status: 429,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      if (response.status === 402) {
        return new Response(JSON.stringify({ error: "Krediter slut, vänligen fyll på." }), {
          status: 402,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const errorText = await response.text();
      console.error("AI gateway error:", response.status, errorText);
      throw new Error(`AI gateway error: ${response.status}`);
    }

    const data = await response.json();
    
    // Extract the tool call result
    const toolCall = data.choices?.[0]?.message?.tool_calls?.[0];
    if (!toolCall || toolCall.function.name !== "generate_leads") {
      throw new Error("Unexpected AI response format");
    }

    const leads = JSON.parse(toolCall.function.arguments);

    return new Response(JSON.stringify(leads), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Error generating leads:", error);
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
