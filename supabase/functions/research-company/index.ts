import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { requireAdmin } from "../_shared/admin-auth.ts";

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

interface CompanyResearchRequest {
  company_name: string;
  district: string;
  industry: string;
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  const auth = await requireAdmin(req, corsHeaders);
  if (!auth.ok) return auth.response;

  try {

    const FIRECRAWL_API_KEY = Deno.env.get("FIRECRAWL_API_KEY");
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!FIRECRAWL_API_KEY) throw new Error("FIRECRAWL_API_KEY is not configured");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY is not configured");

    const { company_name, district, industry }: CompanyResearchRequest = await req.json();
    if (!company_name) throw new Error("company_name is required");

    // Storstockholm-kontroll
    const allowed = new Set(STORSTOCKHOLM.map((s) => s.toLowerCase()));
    if (!allowed.has(String(district || "").toLowerCase().trim())) {
      return new Response(
        JSON.stringify({
          error: `Vi kontaktar endast företag i Storstockholm. "${district}" ligger utanför området.`,
        }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    console.log(`Researching company: ${company_name} (${district})`);

    // Steg 1: Research via Firecrawl
    const searchResponse = await fetch("https://api.firecrawl.dev/v1/search", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${FIRECRAWL_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: `${company_name} ${district} Stockholm företag verksamhet`,
        limit: 3,
        scrapeOptions: { formats: ["markdown"] },
      }),
    });

    let companyInfo = "";
    if (searchResponse.ok) {
      const searchData = await searchResponse.json();
      companyInfo = searchData.data?.slice(0, 2)
        .map((r: any) => r.markdown || r.description).join("\n\n") || "";
    } else {
      console.error("Firecrawl search error:", await searchResponse.text());
    }

    // Slumpad variation för att undvika mall-liknande utskick
    const openingStyles = [
      "börja med en konkret observation om företaget",
      "börja med en fråga om deras vardag på kontoret",
      "börja med ett kort konstaterande – aldrig med hälsningsfras",
      "börja med en referens till deras bransch eller uppdrag",
    ];
    const ctaStyles = [
      '"Skulle det här kunna passa ert kontor?"',
      '"Vill ni att jag skickar lite mer information?"',
      '"Har ni redan en lösning för fika på kontoret?"',
      '"Kan jag höra av mig med ett förslag?"',
      '"Är det intressant för er?"',
    ];
    const opening = openingStyles[Math.floor(Math.random() * openingStyles.length)];
    const cta = ctaStyles[Math.floor(Math.random() * ctaStyles.length)];
    const mentionTiffanyAge = Math.random() < 0.35; // ibland, aldrig alltid

    // Steg 2: Generera personligt mejl enligt masterprompt
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
            content: `Du agerar som en av världens bästa B2B-säljare, copywriter och SDR för Lennart Svenssons Konditorivaror – ett bageri i Stockholm som levererar färska handgjorda kakor på veckoabonnemang till kontor i Storstockholm.

MÅL: få mottagaren att svara på mejlet eller vilja veta mer om kakabonnemanget.

MÅLGRUPP: endast företag i Storstockholm. Skriv aldrig till någon utanför området.

SPRÅK: korrekt, professionell och naturlig svenska. Skriv som en människa – aldrig som en AI.

RESEARCH: använd endast information som går att verifiera i researchmaterialet nedan. Hitta ALDRIG på fakta, siffror, namn eller händelser. Om du inte har säker info – håll det generellt om deras bransch utan att påstå specifika detaljer.

VARIATION (kritisk regel – två företag får aldrig få samma mejl):
- Detta mejl ska ${opening}.
- Använd följande CTA (variera formuleringen lätt om det passar): ${cta}
- Variera alltid inledning, disposition, formuleringar, argument och avslut.

TON:
- Professionell, vänlig, personlig, självsäker, kort, lätt att läsa.
- Undvik säljklyschor, spamord, överdrifter, "Jag hoppas allt är bra", "Jag tänkte bara...", och AI-liknande formuleringar.
- Använd inte många utropstecken, versaler eller överdrivna löften.

PRODUKTVÄRDE (välj det som passar företaget, inte alla på en gång):
- Färska handgjorda kakor
- Leverans direkt till arbetsplatsen varje vecka
- Enkelt abonnemang, ingen administration
- Uppskattat av personal, skapar trivsel på kontoret
- Sparar tid för den som annars ordnar fikat

AVSÄNDARE: Tiffany. ${mentionTiffanyAge ? "I detta mejl får du nämna att Tiffany är 16 år och driver företaget – men bara om det glider in naturligt, aldrig för att skapa medlidande." : "Nämn inte Tiffanys ålder i detta mejl."}

SIGNATUR: avsluta alltid med:
Vänliga hälsningar,
Tiffany
Lennart Svenssons Konditorivaror

Använd ALDRIG platshållare som "(ditt namn)".

LÄNGD: max ca 130 ord i brödtexten.

CTA: exakt en fråga i slutet.`,
          },
          {
            role: "user",
            content: `Skriv ett unikt kall-mejl till:
Företag: ${company_name}
Bransch: ${industry}
Kommun (Storstockholm): ${district}

Researchmaterial (endast dessa fakta är verifierade – hitta inte på mer):
${companyInfo || "Ingen specifik information hittad. Håll mejlet generellt kring branschen utan att påstå specifika detaljer om företaget."}`,
          },
        ],
        tools: [
          {
            type: "function",
            function: {
              name: "generate_email",
              description: "Genererar ett unikt personligt kall-mejl enligt masterprompten",
              parameters: {
                type: "object",
                properties: {
                  subject: {
                    type: "string",
                    description: "Kort, mänsklig ämnesrad utan spamord eller utropstecken",
                  },
                  body: {
                    type: "string",
                    description: "Mejlets brödtext, inkl. signatur från Tiffany",
                  },
                  personalization_points: {
                    type: "array",
                    items: { type: "string" },
                    description: "Verifierbara punkter från researchen som mejlet bygger på",
                  },
                },
                required: ["subject", "body", "personalization_points"],
                additionalProperties: false,
              },
            },
          },
        ],
        tool_choice: { type: "function", function: { name: "generate_email" } },
      }),
    });

    if (!emailResponse.ok) {
      if (emailResponse.status === 429) {
        return new Response(JSON.stringify({ error: "Rate limit överskriden, försök igen senare." }), {
          status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      if (emailResponse.status === 402) {
        return new Response(JSON.stringify({ error: "Krediter slut, vänligen fyll på." }), {
          status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" },
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
      email: emailContent,
    }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
  } catch (error) {
    console.error("Error researching company:", error);
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
