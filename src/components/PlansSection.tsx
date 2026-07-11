import { useState, useMemo, useEffect } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "sonner";
import { z } from "zod";

const PRICE_PER_KG = 325;
const KG_PER_EMPLOYEE = 0.3;

const isStockholmPostalCode = (postalCode: string) => {
  const cleaned = postalCode.replace(/\s/g, "");
  if (!/^\d{5}$/.test(cleaned)) return false;
  const num = parseInt(cleaned, 10);
  return num >= 10000 && num <= 19999;
};

const formSchema = z.object({
  företag: z.string().trim().min(1, "Fyll i företagsnamn").max(100),
  epost: z.string().trim().email("Ange en giltig e-postadress").max(255),
  telefon: z.string().trim().max(30).optional(),
  adress: z.string().trim().max(200).optional(),
  postnummer: z
    .string()
    .trim()
    .min(1, "Fyll i postnummer")
    .refine(isStockholmPostalCode, "Vi levererar endast inom Storstockholm (100 00 – 199 99)"),
  stad: z.string().trim().max(100).optional(),
  kommentarer: z.string().trim().max(1000).optional(),
});

const PlansSection = () => {
  const { user } = useAuth();
  const [employees, setEmployees] = useState(10);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
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

  // Prefyll från profil om inloggad
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

    setSubmitting(true);
    try {
      const { data, error } = await supabase.functions.invoke("submit-order", {
        body: {
          ...result.data,
          employees,
          kg_per_vecka: recommendedKg,
          pris_per_vecka: weeklyPrice,
        },
      });
      if (error) throw error;
      if ((data as any)?.error) throw new Error((data as any).error);
      setSubmitted(true);
    } catch (err) {
      console.error(err);
      toast.error("Kunde inte skicka beställningen. Försök igen.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section id="abonnemang" className="py-16 md:py-28 px-6 bg-background">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10 md:mb-14">
          <div className="w-24 h-px bg-primary/40 mx-auto mb-6"></div>
          <h2 className="font-display text-3xl md:text-5xl font-semibold mb-4">
            Hur många anställda har ni?
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-xl mx-auto">
            Vi rekommenderar automatiskt rätt mängd kakor utifrån antalet medarbetare.
          </p>
        </div>

        {/* Calculator card */}
        <div className="bg-card border border-border rounded-sm shadow-[0_10px_40px_-15px_rgba(0,0,0,0.15)] p-6 md:p-12">
          {submitted ? (
            <div className="text-center py-8 animate-fade-in">
              <CheckCircle2 className="w-16 h-16 text-primary mx-auto mb-4" />
              <h3 className="font-display text-3xl md:text-4xl font-semibold mb-3">
                Tack för din beställning!
              </h3>
              <p className="text-muted-foreground max-w-md mx-auto">
                Vi har tagit emot din förfrågan för{" "}
                <strong className="text-foreground">
                  {recommendedKg} kg kakor per vecka
                </strong>{" "}
                och kontaktar dig inom kort för att bekräfta leverans.
              </p>
            </div>
          ) : !showForm ? (
            <>
              {/* Employee count */}
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

              {/* Slider */}
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

              {/* Result */}
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
                    Pris per vecka
                  </div>
                  <div className="font-display text-3xl md:text-4xl font-semibold text-primary tabular-nums">
                    {weeklyPrice.toLocaleString("sv-SE")} kr
                  </div>
                  <div className="text-muted-foreground text-xs mt-1">exklusive moms</div>
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
                  Din beställning
                </div>
                <div className="font-display text-2xl md:text-3xl font-semibold">
                  {recommendedKg} kg/vecka —{" "}
                  <span className="text-primary">
                    {weeklyPrice.toLocaleString("sv-SE")} kr
                  </span>
                </div>
                <div className="text-muted-foreground text-xs">
                  exklusive moms · {employees} {employees === 1 ? "anställd" : "anställda"}
                </div>
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
                <label className="block mb-1.5 text-sm font-semibold">Leveransadress</label>
                <input
                  name="adress"
                  value={form.adress}
                  onChange={handleChange}
                  className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block mb-1.5 text-sm font-semibold">
                    Postnummer <span className="text-primary">*</span>
                  </label>
                  <input
                    name="postnummer"
                    placeholder="t.ex. 114 32"
                    value={form.postnummer}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {errors.postnummer && (
                    <p className="text-destructive text-xs mt-1">{errors.postnummer}</p>
                  )}
                </div>
                <div>
                  <label className="block mb-1.5 text-sm font-semibold">Stad</label>
                  <input
                    name="stad"
                    value={form.stad}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-sm bg-background border border-border focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
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
                      Skickar...
                    </>
                  ) : (
                    "Skicka beställning"
                  )}
                </button>
              </div>
              <p className="text-center text-muted-foreground text-xs">
                Vi kontaktar dig för att bekräfta leverans och betalning.
              </p>
            </form>
          )}
        </div>
      </div>
    </section>
  );
};

export default PlansSection;
