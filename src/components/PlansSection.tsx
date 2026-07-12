import { useState, useMemo, useEffect } from "react";
import { Loader2, CheckCircle2, CreditCard, FileText, ChevronsUpDown, Check } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "sonner";
import { z } from "zod";
import { StripeEmbeddedCheckout } from "@/components/StripeEmbeddedCheckout";
import { getStripeEnvironment, hasPaymentsConfigured } from "@/lib/stripe";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { cn } from "@/lib/utils";

const STORSTOCKHOLM_CITIES = [
  "Stockholm", "Solna", "Sundbyberg", "Nacka", "Lidingö", "Danderyd",
  "Täby", "Sollentuna", "Järfälla", "Upplands Väsby", "Sigtuna",
  "Vallentuna", "Österåker", "Vaxholm", "Värmdö", "Tyresö", "Haninge",
  "Nynäshamn", "Botkyrka", "Salem", "Södertälje", "Nykvarn", "Huddinge",
  "Bromma", "Ekerö", "Upplands-Bro",
];

const PRICE_PER_KG_EXKL = 325; // exkl. moms, används för Stripe/faktura
const VAT_RATE = 0.25;
const PRICE_PER_KG = PRICE_PER_KG_EXKL * (1 + VAT_RATE); // 406,25 kr ink moms – visas för kunden
const KG_PER_EMPLOYEE = 0.3;
const WEEKS_PER_MONTH = 4;

const isStockholmPostalCode = (postalCode: string) => {
  const cleaned = postalCode.replace(/\s/g, "");
  if (!/^\d{5}$/.test(cleaned)) return false;
  const num = parseInt(cleaned, 10);
  return num >= 10000 && num <= 19999;
};

const stockholmDeliveryMessage = "Vi levererar endast till företag inom Storstockholm.";

const formSchema = z.object({
  företag: z.string().trim().min(1, "Fyll i företagsnamn").max(100),
  epost: z.string().trim().email("Ange en giltig e-postadress").max(255),
  telefon: z.string().trim().max(30).optional(),
  adress: z.string().trim().min(1, "Fyll i leveransadress").max(200),
  postnummer: z
    .string()
    .trim()
    .min(1, "Fyll i postnummer")
    .refine(isStockholmPostalCode, "Vi levererar endast inom Storstockholm (100 00 – 199 99)"),
  stad: z.string().trim().min(1, "Fyll i stad").max(100),
  kommentarer: z.string().trim().max(1000).optional(),
});

type Method = "card" | "invoice";

const PlansSection = () => {
  const { user } = useAuth();
  const [employees, setEmployees] = useState(10);
  const [showForm, setShowForm] = useState(false);
  const [method, setMethod] = useState<Method>("card");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<null | "card" | "invoice">(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [form, setForm] = useState({
    företag: "",
    epost: "",
    telefon: "",
    adress: "",
    postnummer: "",
    stad: "",
    kommentarer: "",
  });

  const recommendedKg = useMemo(
    () => Math.max(1, Math.round(employees * KG_PER_EMPLOYEE)),
    [employees]
  );
  const weeklyPrice = recommendedKg * PRICE_PER_KG;
  const monthlyPrice = weeklyPrice * WEEKS_PER_MONTH;

  useEffect(() => {
    if (!user || !showForm) return;
    (async () => {
      const { data } = await supabase
        .from("profiles")
        .select("company_name, phone, street_address, postal_code, city")
        .eq("user_id", user.id)
        .maybeSingle();
      setForm((prev) => ({
        ...prev,
        företag: prev.företag || data?.company_name || "",
        epost: prev.epost || user.email || "",
        telefon: prev.telefon || data?.phone || "",
        adress: prev.adress || data?.street_address || "",
        postnummer: prev.postnummer || data?.postal_code || "",
        stad: prev.stad || data?.city || "",
      }));
    })();
  }, [user, showForm]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setForm((p) => ({ ...p, [name]: value }));
    if (errors[name]) setErrors((p) => ({ ...p, [name]: "" }));
    if (name === "postnummer" && errors.postnummer) {
      setErrors((p) => ({ ...p, postnummer: "" }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = formSchema.safeParse(form);
    if (!result.success) {
      const fe: Record<string, string> = {};
      result.error.errors.forEach((err) => {
        if (err.path[0]) fe[err.path[0] as string] = err.message;
      });
      setErrors(fe);
      return;
    }

    if (!hasPaymentsConfigured()) {
      toast.error("Betalningar är inte konfigurerade ännu.");
      return;
    }

    setSubmitting(true);
    try {
      const body = {
        method,
        employees,
        kg_per_week: recommendedKg,
        company: result.data.företag,
        email: result.data.epost,
        phone: result.data.telefon ?? "",
        address: result.data.adress,
        postal_code: result.data.postnummer,
        city: result.data.stad,
        comments: result.data.kommentarer ?? "",
        return_url: `${window.location.origin}/order-confirmation?session_id={CHECKOUT_SESSION_ID}&method=card&kg=${recommendedKg}&email=${encodeURIComponent(result.data.epost)}`,
        environment: getStripeEnvironment(),
      };

      const { data, error } = await supabase.functions.invoke("create-checkout", { body });
      if (error) throw error;
      if ((data as any)?.error) throw new Error((data as any).error);

      if (method === "card") {
        if (!(data as any)?.clientSecret) throw new Error("Kunde inte skapa checkout-session");
        setClientSecret((data as any).clientSecret);
      } else {
        window.location.href = `/order-confirmation?method=invoice&kg=${recommendedKg}&email=${encodeURIComponent(result.data.epost)}`;
        return;
      }
    } catch (err: any) {
      console.error(err);
      toast.error(err?.message || "Kunde inte starta abonnemang. Försök igen.");
    } finally {
      setSubmitting(false);
    }
  };

  // Show embedded checkout after we get clientSecret
  if (clientSecret) {
    return (
      <section id="abonnemang" className="py-16 md:py-28 px-6 bg-background">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-8">
            <div className="w-24 h-px bg-primary/40 mx-auto mb-6"></div>
            <h2 className="font-display text-3xl md:text-5xl font-semibold mb-2">
              Slutför betalning
            </h2>
            <p className="text-muted-foreground text-sm">
              {recommendedKg} kg/vecka · {monthlyPrice.toLocaleString("sv-SE")} kr/månad (ink moms)
            </p>
          </div>
          <div className="bg-card border border-border rounded-sm p-4 md:p-6">
            <StripeEmbeddedCheckout fetchClientSecret={async () => clientSecret} />
          </div>
          <div className="text-center mt-4">
            <button
              onClick={() => setClientSecret(null)}
              className="text-sm text-muted-foreground underline hover:text-foreground"
            >
              ← Avbryt och gå tillbaka
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section id="abonnemang" className="py-16 md:py-28 px-6 bg-background">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-10 md:mb-14">
          <div className="w-24 h-px bg-primary/40 mx-auto mb-6"></div>
          <h2 className="font-display text-3xl md:text-5xl font-semibold mb-4">
            Hur många anställda har ni?
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-xl mx-auto">
            Vi rekommenderar automatiskt rätt mängd kakor utifrån antalet medarbetare.
          </p>
        </div>

        <div className="bg-card border border-border rounded-sm shadow-[0_10px_40px_-15px_rgba(0,0,0,0.15)] p-6 md:p-12">
          {submitted === "invoice" ? (
            <div className="text-center py-8 animate-fade-in">
              <CheckCircle2 className="w-16 h-16 text-primary mx-auto mb-4" />
              <h3 className="font-display text-3xl md:text-4xl font-semibold mb-3">
                Abonnemang startat!
              </h3>
              <p className="text-muted-foreground max-w-md mx-auto">
                Vi har skapat ditt abonnemang på{" "}
                <strong className="text-foreground">
                  {recommendedKg} kg kakor per vecka
                </strong>
                . Första fakturan skickas till <strong>{form.epost}</strong> inom kort.
              </p>
            </div>
          ) : !showForm ? (
            <>
              <div className="text-center mb-8">
                <div
                  key={employees}
                  className="font-display text-6xl md:text-8xl font-semibold text-primary tabular-nums animate-fade-in"
                >
                  {employees}
                </div>
                <div className="text-muted-foreground text-sm md:text-base mt-2 tracking-wide uppercase">
                  {employees === 1 ? "anställd" : "anställda"}
                </div>
              </div>

              <div className="mb-10 md:mb-12">
                <input
                  type="range"
                  min={1}
                  max={100}
                  step={1}
                  value={employees}
                  onChange={(e) => setEmployees(parseInt(e.target.value, 10))}
                  className="calculator-slider w-full"
                  aria-label="Antal anställda"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-3">
                  <span>1</span>
                  <span>100</span>
                </div>
              </div>

              <div className="text-center border-t border-border pt-8 md:pt-10 space-y-6">
                <div>
                  <div className="text-muted-foreground text-xs md:text-sm uppercase tracking-widest mb-2">
                    Rekommenderad mängd
                  </div>
                  <div className="font-display text-4xl md:text-5xl font-semibold text-foreground tabular-nums">
                    {recommendedKg} kg
                  </div>
                  <div className="text-muted-foreground text-sm mt-1">per vecka</div>
                </div>

                <div>
                  <div className="text-muted-foreground text-xs md:text-sm uppercase tracking-widest mb-2">
                    Pris per månad
                  </div>
                  <div className="font-display text-3xl md:text-4xl font-semibold text-primary tabular-nums">
                    {monthlyPrice.toLocaleString("sv-SE")} kr
                  </div>
                  <div className="text-muted-foreground text-xs mt-1">
                    ink moms
                  </div>
                </div>

                <button
                  onClick={() => setShowForm(true)}
                  className="btn-classic w-full py-4 text-base md:text-lg rounded-sm mt-2"
                >
                  Starta abonnemang
                </button>
              </div>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5 animate-fade-in">
              <div className="text-center mb-2">
                <div className="text-muted-foreground text-xs uppercase tracking-widest mb-1">
                  Ditt abonnemang
                </div>
                <div className="font-display text-2xl md:text-3xl font-semibold">
                  {recommendedKg} kg/vecka —{" "}
                  <span className="text-primary">
                    {monthlyPrice.toLocaleString("sv-SE")} kr/mån
                  </span>
                </div>
                <div className="text-muted-foreground text-xs">
                  ink moms · {employees} {employees === 1 ? "anställd" : "anställda"}
                </div>
              </div>

              {/* Betalningsmetod */}
              <div>
                <label className="block mb-2 text-sm font-semibold">Betalningsmetod</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setMethod("card")}
                    className={`flex items-center gap-3 p-4 rounded-sm border text-left transition-colors ${
                      method === "card"
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <CreditCard className="w-5 h-5 text-primary" />
                    <div>
                      <div className="font-semibold text-sm">Kort</div>
                      <div className="text-xs text-muted-foreground">
                        Automatiskt varje månad
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setMethod("invoice")}
                    className={`flex items-center gap-3 p-4 rounded-sm border text-left transition-colors ${
                      method === "invoice"
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <FileText className="w-5 h-5 text-primary" />
                    <div>
                      <div className="font-semibold text-sm">Faktura</div>
                      <div className="text-xs text-muted-foreground">
                        Månadsvis via e-post
                      </div>
                    </div>
                  </button>
                </div>
              </div>

              <div className="border border-primary/30 bg-primary/5 px-4 py-3 rounded-sm text-sm text-foreground">
                {stockholmDeliveryMessage} Ange postnummer 100 00–199 99 för att gå vidare.
              </div>

              <div>
                <label className="block mb-1.5 text-sm font-semibold">
                  Företagsnamn <span className="text-primary">*</span>
                </label>
                <input
                  name="företag"
                  value={form.företag}
                  onChange={handleChange}
                  className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                {errors.företag && (
                  <p className="text-destructive text-xs mt-1">{errors.företag}</p>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block mb-1.5 text-sm font-semibold">
                    E-post <span className="text-primary">*</span>
                  </label>
                  <input
                    type="email"
                    name="epost"
                    value={form.epost}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {errors.epost && (
                    <p className="text-destructive text-xs mt-1">{errors.epost}</p>
                  )}
                </div>
                <div>
                  <label className="block mb-1.5 text-sm font-semibold">Telefon</label>
                  <input
                    type="tel"
                    name="telefon"
                    value={form.telefon}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
              </div>

              <div>
                <label className="block mb-1.5 text-sm font-semibold">
                  Leveransadress <span className="text-primary">*</span>
                </label>
                <input
                  name="adress"
                  placeholder="Gatuadress, t.ex. Kungsgatan 12"
                  value={form.adress}
                  onChange={handleChange}
                  aria-invalid={!!errors.adress}
                  className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                {errors.adress && (
                  <p className="text-destructive text-xs mt-1">{errors.adress}</p>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block mb-1.5 text-sm font-semibold">
                    Postnummer <span className="text-primary">*</span>
                  </label>
                  <input
                    name="postnummer"
                    placeholder="t.ex. 114 32"
                    value={form.postnummer}
                    onChange={handleChange}
                    aria-invalid={!!errors.postnummer}
                    className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {errors.postnummer && (
                    <p className="text-destructive text-xs mt-1">{errors.postnummer}</p>
                  )}
                  <p className="text-muted-foreground text-xs mt-1">
                    Endast postnummer inom Storstockholm.
                  </p>
                </div>
                <div>
                  <label className="block mb-1.5 text-sm font-semibold">
                    Stad <span className="text-primary">*</span>
                  </label>
                  <input
                    name="stad"
                    placeholder="t.ex. Stockholm"
                    value={form.stad}
                    onChange={handleChange}
                    aria-invalid={!!errors.stad}
                    className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {errors.stad && (
                    <p className="text-destructive text-xs mt-1">{errors.stad}</p>
                  )}
                </div>
              </div>

              <div>
                <label className="block mb-1.5 text-sm font-semibold">Kommentarer</label>
                <textarea
                  name="kommentarer"
                  value={form.kommentarer}
                  onChange={handleChange}
                  rows={3}
                  className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  disabled={submitting}
                  className="sm:w-1/3 py-3 rounded-sm border border-border hover:bg-muted text-sm"
                >
                  ← Tillbaka
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-classic flex-1 py-3 rounded-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {method === "card" ? "Öppnar betalning..." : "Startar abonnemang..."}
                    </>
                  ) : method === "card" ? (
                    "Fortsätt till betalning"
                  ) : (
                    "Starta abonnemang (faktura)"
                  )}
                </button>
              </div>
              <p className="text-center text-muted-foreground text-xs">
                Alla priser inklusive moms (25%).
              </p>
            </form>
          )}
        </div>
      </div>
    </section>
  );
};

export default PlansSection;
