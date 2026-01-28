import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

interface CompanyResearchRequest {
  company_name: string;
  district: string;
  industry: string;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const FIRECRAWL_API_KEY = Deno.env.get("FIRECRAWL_API_KEY");
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");

    if (!FIRECRAWL_API_KEY) {
      throw new Error("FIRECRAWL_API_KEY is not configured");
    }
    if (!LOVABLE_API_KEY) {
      throw new Error("LOVABLE_API_KEY is not configured");
    }

    const { company_name, district, industry }: CompanyResearchRequest = await req.json();

    if (!company_name) {
      throw new Error("company_name is required");
    }

    console.log(`Researching company: ${company_name}`);

    // Step 1: Search for company website using Firecrawl
    const searchResponse = await fetch("https://api.firecrawl.dev/v1/search", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${FIRECRAWL_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: `${company_name} ${district} Stockholm företag`,
        limit: 3,
        scrapeOptions: {
          formats: ["markdown"],
        },
      }),
    });

    if (!searchResponse.ok) {
      const errorText = await searchResponse.text();
      console.error("Firecrawl search error:", errorText);
      throw new Error(`Firecrawl search failed: ${searchResponse.status}`);
    }

    const searchData = await searchResponse.json();
    const companyInfo = searchData.data?.slice(0, 2).map((result: any) => result.markdown || result.description).join("\n\n") || "";

    console.log(`Found company info: ${companyInfo.substring(0, 200)}...`);

    // Step 2: Generate personalized email using Lovable AI
    const emailResponse = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
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
            content: `Du är en erfaren B2B-säljare för ett bageri i Stockholm som levererar färska kakor till företag.
            
Din uppgift är att skriva ett personligt och engagerande kall-mejl till potentiella kunder.

Regler:
- Håll mejlet kort (max 150 ord)
- Var personlig och referera till specifik info om företaget
- Nämn att vi levererar färska kakor varje vecka
- Föreslå ett möte eller provleverans
- Avsluta med en tydlig call-to-action
- Skriv på svenska
- Var professionell men varm i tonen`
          },
          {
            role: "user",
            content: `Skriv ett personligt kall-mejl till:
Företag: ${company_name}
Bransch: ${industry}
Område: ${district}

Information om företaget:
${companyInfo || "Ingen specifik information hittad, använd generella branschinsikter."}`
          }
        ],
        tools: [
          {
            type: "function",
            function: {
              name: "generate_email",
              description: "Genererar ett personligt kall-mejl",
              parameters: {
                type: "object",
                properties: {
                  subject: { type: "string", description: "Mejlets ämnesrad" },
                  body: { type: "string", description: "Mejlets innehåll" },
                  personalization_points: {
                    type: "array",
                    items: { type: "string" },
                    description: "Punkter som gör mejlet personligt"
                  }
                },
                required: ["subject", "body", "personalization_points"],
                additionalProperties: false
              }
            }
          }
        ],
        tool_choice: { type: "function", function: { name: "generate_email" } }
      }),
    });

    if (!emailResponse.ok) {
      if (emailResponse.status === 429) {
        return new Response(JSON.stringify({ error: "Rate limit överskriden, försök igen senare." }), {
          status: 429,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      if (emailResponse.status === 402) {
        return new Response(JSON.stringify({ error: "Krediter slut, vänligen fyll på." }), {
          status: 402,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const errorText = await emailResponse.text();
      console.error("AI gateway error:", emailResponse.status, errorText);
      throw new Error(`AI gateway error: ${emailResponse.status}`);
    }

    const emailData = await emailResponse.json();
    const toolCall = emailData.choices?.[0]?.message?.tool_calls?.[0];
    
    if (!toolCall || toolCall.function.name !== "generate_email") {
      throw new Error("Unexpected AI response format");
    }

    const emailContent = JSON.parse(toolCall.function.arguments);

    return new Response(JSON.stringify({
      success: true,
      company_name,
      research_summary: companyInfo.substring(0, 500),
      email: emailContent
    }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Error researching company:", error);
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
