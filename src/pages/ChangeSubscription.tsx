import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { getStripeEnvironment, hasPaymentsConfigured } from "@/lib/stripe";
import Header from "@/components/Header";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2 } from "lucide-react";

const PRICE_PER_KG_EXKL = 325;
const VAT_RATE = 0.25;
const PRICE_PER_KG_INK = PRICE_PER_KG_EXKL * (1 + VAT_RATE);
const WEEKS_PER_MONTH = 4;

const ChangeSubscription = () => {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const { toast } = useToast();
  const [currentKg, setCurrentKg] = useState<number | null>(null);
  const [newKg, setNewKg] = useState<number>(10);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) navigate("/");
  }, [authLoading, user, navigate]);

  useEffect(() => {
    (async () => {
      if (!user) return;
      const env = hasPaymentsConfigured() ? getStripeEnvironment() : "sandbox";
      const { data } = await supabase
        .from("subscriptions")
        .select("kg_per_week, status")
        .eq("user_id", user.id)
        .eq("environment", env)
        .in("status", ["active", "trialing", "past_due"])
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle();

      if (!data) {
        toast({
          title: "Inget aktivt abonnemang",
          description: "Du behöver ett aktivt abonnemang för att ändra mängd.",
          variant: "destructive",
        });
        navigate("/account");
        return;
      }
      const kg = Number(data.kg_per_week ?? 10);
      setCurrentKg(kg);
      setNewKg(kg);
      setLoading(false);
    })();
  }, [user, navigate, toast]);

  const newMonthlyInk = useMemo(
    () => newKg * WEEKS_PER_MONTH * PRICE_PER_KG_INK,
    [newKg],
  );
  const currentMonthlyInk = useMemo(
    () => (currentKg ?? 0) * WEEKS_PER_MONTH * PRICE_PER_KG_INK,
    [currentKg],
  );
  const diff = newMonthlyInk - currentMonthlyInk;
  const unchanged = currentKg !== null && newKg === currentKg;

  const handleSave = async () => {
    if (!hasPaymentsConfigured()) {
      toast({ title: "Betalningar inte konfigurerade", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      const { data, error } = await supabase.functions.invoke("update-subscription-quantity", {
        body: { new_kg_per_week: newKg, environment: getStripeEnvironment() },
      });
      if (error) throw error;
      if ((data as any)?.error) throw new Error((data as any).error);
      toast({
        title: "Abonnemang uppdaterat",
        description: `Ny mängd: ${newKg} kg/vecka. Prisdifferens justeras på nästa faktura.`,
      });
      navigate("/account");
    } catch (e: any) {
      toast({
        title: "Kunde inte uppdatera",
        description: e?.message ?? String(e),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="pt-24 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <div className="pt-24 px-4 pb-16">
        <div className="max-w-2xl mx-auto">
          <button
            type="button"
            onClick={() => navigate("/account")}
            className="text-sm text-muted-foreground hover:underline mb-6 flex items-center gap-1"
          >
            <ArrowLeft className="w-4 h-4" /> Tillbaka till mitt konto
          </button>

          <div className="text-center mb-8">
            <div className="w-24 h-px bg-primary/40 mx-auto mb-6" />
            <h1 className="font-display text-3xl md:text-5xl font-semibold mb-2">
              Ändra abonnemang
            </h1>
            <p className="text-muted-foreground font-display italic">
              Justera antal kg kakor per vecka
            </p>
          </div>

          <div className="bg-card border border-border rounded-sm p-6 md:p-10 shadow-[0_10px_40px_-15px_rgba(0,0,0,0.15)] space-y-8">
            <div className="text-center">
              <div className="text-muted-foreground text-xs uppercase tracking-widest mb-2">
                Ny mängd
              </div>
              <div
                key={newKg}
                className="font-display text-6xl md:text-7xl font-semibold text-primary tabular-nums animate-fade-in"
              >
                {newKg} kg
              </div>
              <div className="text-muted-foreground text-sm mt-1">per vecka</div>
            </div>

            <div>
              <input
                type="range"
                min={1}
                max={100}
                step={1}
                value={newKg}
                onChange={(e) => setNewKg(parseInt(e.target.value, 10))}
                className="calculator-slider w-full"
                aria-label="Kg per vecka"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-3">
                <span>1 kg</span>
                <span>100 kg</span>
              </div>
            </div>

            <div className="border-t border-border pt-6 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Nuvarande månadskostnad</span>
                <span className="font-medium tabular-nums">
                  {Math.round(currentMonthlyInk).toLocaleString("sv-SE")} kr
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Ny månadskostnad</span>
                <span className="font-medium tabular-nums text-primary">
                  {Math.round(newMonthlyInk).toLocaleString("sv-SE")} kr
                </span>
              </div>
              {!unchanged && (
                <div className="flex justify-between text-sm border-t border-border pt-3">
                  <span className="text-muted-foreground">Skillnad</span>
                  <span
                    className={`font-semibold tabular-nums ${
                      diff > 0 ? "text-foreground" : "text-primary"
                    }`}
                  >
                    {diff > 0 ? "+" : ""}
                    {Math.round(diff).toLocaleString("sv-SE")} kr/mån
                  </span>
                </div>
              )}
              <p className="text-xs text-muted-foreground text-center pt-2">
                ink moms · prisdifferens proportioneras på nästa faktura
              </p>
            </div>

            <Button
              onClick={handleSave}
              disabled={saving || unchanged}
              className="w-full py-6 text-base"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Uppdaterar...
                </>
              ) : unchanged ? (
                "Ingen ändring gjord"
              ) : (
                `Bekräfta ${newKg} kg/vecka`
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChangeSubscription;
