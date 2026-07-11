import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { getStripeEnvironment, hasPaymentsConfigured } from "@/lib/stripe";
import Header from "@/components/Header";
import { Save, Package, ExternalLink } from "lucide-react";


// Validate Stockholm postal codes (100 00 - 199 99)
const isStockholmPostalCode = (postalCode: string) => {
  if (!postalCode || postalCode.trim() === "") return true; // Allow empty
  const cleaned = postalCode.replace(/\s/g, "");
  if (!/^\d{5}$/.test(cleaned)) return false;
  const num = parseInt(cleaned, 10);
  return num >= 10000 && num <= 19999;
};

const profileSchema = z.object({
  company_name: z.string().trim().max(100, { message: "Företagsnamn får max vara 100 tecken" }).optional(),
  street_address: z.string().trim().max(200, { message: "Gatuadress får max vara 200 tecken" }).optional(),
  postal_code: z
    .string()
    .trim()
    .max(10, { message: "Postnummer får max vara 10 tecken" })
    .refine((val) => isStockholmPostalCode(val), {
      message: "Vi levererar endast inom Storstockholm (100 00 – 199 99)",
    })
    .optional(),
  city: z.string().trim().max(100, { message: "Ort får max vara 100 tecken" }).optional(),
});

interface ProfileData {
  company_name: string;
  street_address: string;
  postal_code: string;
  city: string;
}

const getPostalCodeError = (postalCode: string) => {
  if (!postalCode || postalCode.trim() === "") return null;
  const cleaned = postalCode.replace(/\s/g, "");
  if (cleaned.length < 5) return null; // Don't show error while typing
  if (!/^\d{5}$/.test(cleaned)) return "Ange ett giltigt postnummer (5 siffror)";
  const num = parseInt(cleaned, 10);
  if (num < 10000 || num > 19999) {
    return "Vi levererar endast inom Storstockholm (100 00 – 199 99)";
  }
  return null;
};

interface SubscriptionRow {
  id: string;
  status: string;
  kg_per_week: number | null;
  monthly_amount: number | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  collection_method: string | null;
}

const Account = () => {
  const [profile, setProfile] = useState<ProfileData>({
    company_name: "",
    street_address: "",
    postal_code: "",
    city: "",
  });
  const [originalProfile, setOriginalProfile] = useState<ProfileData>({
    company_name: "",
    street_address: "",
    postal_code: "",
    city: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [subscription, setSubscription] = useState<SubscriptionRow | null>(null);
  const [openingPortal, setOpeningPortal] = useState(false);
  const { user, loading: authLoading, signOut } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  

  const hasChanges = 
    profile.company_name !== originalProfile.company_name ||
    profile.street_address !== originalProfile.street_address ||
    profile.postal_code !== originalProfile.postal_code ||
    profile.city !== originalProfile.city;

  useEffect(() => {
    if (!authLoading && !user) {
      navigate("/");
      return;
    }

    if (user) {
      fetchProfile();
      fetchSubscription();
    }
  }, [user, authLoading, navigate]);

  const fetchSubscription = async () => {
    if (!user) return;
    try {
      const env = hasPaymentsConfigured() ? getStripeEnvironment() : "sandbox";
      const { data } = await supabase
        .from("subscriptions")
        .select("id, status, kg_per_week, monthly_amount, current_period_end, cancel_at_period_end, collection_method")
        .eq("user_id", user.id)
        .eq("environment", env)
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      setSubscription((data as SubscriptionRow | null) ?? null);
    } catch (e) {
      console.error("fetchSubscription error:", e);
    }
  };

  const handleManageSubscription = async () => {
    if (!hasPaymentsConfigured()) {
      toast({ title: "Betalningar inte konfigurerade", variant: "destructive" });
      return;
    }
    setOpeningPortal(true);
    try {
      const { data, error } = await supabase.functions.invoke("create-portal-session", {
        body: {
          return_url: `${window.location.origin}/account`,
          environment: getStripeEnvironment(),
        },
      });
      if (error) throw error;
      if ((data as any)?.error) throw new Error((data as any).error);
      const url = (data as any)?.url;
      if (!url) throw new Error("Ingen portal-URL mottagen");
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e: any) {
      toast({
        title: "Kunde inte öppna kundportalen",
        description: e?.message ?? String(e),
        variant: "destructive",
      });
    } finally {
      setOpeningPortal(false);
    }
  };

  const fetchProfile = async () => {
    try {
      const { data, error } = await supabase
        .from("profiles")
        .select("company_name, street_address, postal_code, city")
        .eq("user_id", user!.id)
        .maybeSingle();

      if (error) {
        console.error("Error fetching profile:", error);
        toast({
          title: "Kunde inte hämta profil",
          description: error.message,
          variant: "destructive",
        });
      } else if (data) {
        const profileData = {
          company_name: data.company_name || "",
          street_address: data.street_address || "",
          postal_code: data.postal_code || "",
          city: data.city || "",
        };
        setProfile(profileData);
        setOriginalProfile(profileData);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const validation = profileSchema.safeParse(profile);
    if (!validation.success) {
      toast({
        title: "Fel",
        description: validation.error.errors[0].message,
        variant: "destructive",
      });
      return;
    }

    setIsSaving(true);

    try {
      const { error } = await supabase
        .from("profiles")
        .update({
          company_name: profile.company_name || null,
          street_address: profile.street_address || null,
          postal_code: profile.postal_code || null,
          city: profile.city || null,
        })
        .eq("user_id", user!.id);

      if (error) {
        toast({
          title: "Kunde inte spara profil",
          description: error.message,
          variant: "destructive",
        });
      } else {
        // Navigate to confirmation page after successful save
        navigate("/account/confirmation", { state: { justSaved: true } });
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    navigate("/");
  };

  if (authLoading || isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="pt-24 flex items-center justify-center">
          <p className="text-muted-foreground">Laddar...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <div className="pt-24 px-4 pb-12">
        {/* Back link - top left */}
        <div className="mb-6">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Tillbaka till startsidan
          </button>
        </div>

        <div className="max-w-2xl mx-auto">

          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="font-serif text-3xl md:text-4xl font-semibold mb-2">
              Mitt konto
            </h1>
            <p className="text-muted-foreground">{user?.email}</p>
          </div>

          {/* Profile Card */}
          <div className="bg-card border border-border rounded-lg p-6 md:p-8 shadow-sm mb-6">
            <h2 className="font-serif text-xl mb-6">Mina uppgifter</h2>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="email">E-post</Label>
                <Input
                  id="email"
                  type="email"
                  value={user?.email || ""}
                  disabled
                  className="bg-muted"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="company_name">Företagsnamn</Label>
                <Input
                  id="company_name"
                  type="text"
                  value={profile.company_name}
                  onChange={(e) =>
                    setProfile({ ...profile, company_name: e.target.value })
                  }
                  placeholder="Företagsnamn"
                />
              </div>

              <div className="space-y-4">
                <Label>Leveransadress</Label>
                
                <div className="space-y-2">
                  <Input
                    id="street_address"
                    type="text"
                    value={profile.street_address}
                    onChange={(e) =>
                      setProfile({ ...profile, street_address: e.target.value })
                    }
                    placeholder="Gatuadress"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Input
                      id="postal_code"
                      type="text"
                      value={profile.postal_code}
                      onChange={(e) =>
                        setProfile({ ...profile, postal_code: e.target.value })
                      }
                      placeholder="Postnummer"
                      className={getPostalCodeError(profile.postal_code) ? "border-destructive focus-visible:ring-destructive" : ""}
                    />
                    {getPostalCodeError(profile.postal_code) && (
                      <p className="text-destructive text-xs">
                        {getPostalCodeError(profile.postal_code)}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Input
                      id="city"
                      type="text"
                      value={profile.city}
                      onChange={(e) =>
                        setProfile({ ...profile, city: e.target.value })
                      }
                      placeholder="Ort"
                    />
                  </div>
                </div>

                <p className="text-xs text-muted-foreground">
                  Denna adress används vid beställning av abonnemang.
                </p>
              </div>

              {hasChanges && (
                <Button
                  type="submit"
                  className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                  disabled={isSaving}
                >
                  <Save className="h-4 w-4 mr-2" />
                  {isSaving ? "Sparar..." : "Spara ändringar"}
                </Button>
              )}
            </form>
          </div>

          {/* Subscription Section */}
          <div className="bg-card border border-border rounded-lg p-6 md:p-8 shadow-sm mb-6">
            <div className="flex items-center gap-2 mb-6">
              <Package className="h-5 w-5 text-primary" />
              <h2 className="font-serif text-xl">Mitt abonnemang</h2>
            </div>

            {subscription ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <div className="text-muted-foreground text-xs uppercase tracking-widest">
                      Ditt abonnemang
                    </div>
                    <div className="font-serif text-2xl font-semibold text-foreground">
                      {subscription.kg_per_week ?? "—"} kg / vecka
                    </div>
                    {subscription.monthly_amount && (
                      <div className="text-muted-foreground text-sm">
                        {Math.round(subscription.monthly_amount * 1.25).toLocaleString("sv-SE")} kr/mån ink moms
                        {" · "}
                        {subscription.collection_method === "send_invoice" ? "Faktura" : "Kort"}
                      </div>
                    )}
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded-sm border ${
                      subscription.cancel_at_period_end
                        ? "border-destructive/40 text-destructive"
                        : subscription.status === "past_due"
                        ? "border-amber-500/40 text-amber-700"
                        : "border-primary/40 text-primary"
                    }`}
                  >
                    {subscription.cancel_at_period_end
                      ? "Avslutas vid periodens slut"
                      : subscription.status === "active"
                      ? "Aktiv"
                      : subscription.status === "trialing"
                      ? "Provperiod"
                      : subscription.status === "past_due"
                      ? "Obetald – Stripe försöker igen"
                      : subscription.status === "canceled"
                      ? "Avslutad"
                      : subscription.status}
                  </span>
                </div>

                {subscription.current_period_end && (
                  <p className="text-xs text-muted-foreground">
                    {subscription.cancel_at_period_end || subscription.status === "canceled"
                      ? "Sista leveransperiod till: "
                      : "Nästa förnyelse: "}
                    {new Date(subscription.current_period_end).toLocaleDateString("sv-SE")}
                  </p>
                )}

                <Button
                  onClick={() => navigate("/account/change-subscription")}
                  variant="outline"
                  className="w-full"
                  disabled={subscription.cancel_at_period_end || subscription.status === "canceled"}
                >
                  <Package className="h-4 w-4 mr-2" />
                  Ändra kg/vecka
                </Button>

                <Button
                  onClick={handleManageSubscription}
                  disabled={openingPortal}
                  className="w-full"
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  {openingPortal ? "Öppnar kundportal..." : "Hantera abonnemang"}
                </Button>
                <p className="text-xs text-muted-foreground text-center">
                  Ändra kort, ladda ner fakturor eller säg upp — tillgång kvar till periodens slut.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-muted-foreground text-sm">
                  Du har för närvarande inget aktivt abonnemang.
                </p>
                <Button
                  variant="outline"
                  onClick={() => {
                    navigate("/");
                    setTimeout(() => {
                      const element = document.getElementById("abonnemang");
                      if (element) {
                        element.scrollIntoView({ behavior: "smooth" });
                      }
                    }, 100);
                  }}
                  className="w-full"
                >
                  Beställ abonnemang
                </Button>
              </div>
            )}
          </div>
          <div className="text-center mt-6">
            <button
              type="button"
              onClick={handleSignOut}
              className="text-sm text-destructive hover:underline"
            >
              Logga ut
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Account;
