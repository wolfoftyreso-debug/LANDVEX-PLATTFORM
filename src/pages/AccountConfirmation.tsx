import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { CheckCircle, Package } from "lucide-react";
import Header from "@/components/Header";
import { useAuth } from "@/hooks/useAuth";
import { supabase } from "@/integrations/supabase/client";

interface ProfileData {
  street_address: string;
  postal_code: string;
  city: string;
}

const AccountConfirmation = () => {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) {
      navigate("/");
      return;
    }

    if (user) {
      fetchProfile();
    }
  }, [user, authLoading, navigate]);

  const fetchProfile = async () => {
    try {
      const { data } = await supabase
        .from("profiles")
        .select("street_address, postal_code, city")
        .eq("user_id", user!.id)
        .maybeSingle();

      if (data) {
        setProfile({
          street_address: data.street_address || "",
          postal_code: data.postal_code || "",
          city: data.city || "",
        });
      }
    } finally {
      setIsLoading(false);
    }
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
        {/* Back link */}
        <div className="mb-6">
          <button
            type="button"
            onClick={() => navigate("/account")}
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Tillbaka till mitt konto
          </button>
        </div>

        <div className="max-w-2xl mx-auto">
          {/* Success message */}
          <div className="bg-card border border-border rounded-lg p-6 md:p-8 shadow-sm mb-6">
            <div className="flex items-center gap-4 mb-4">
              <CheckCircle className="h-8 w-8 text-primary flex-shrink-0" />
              <div>
                <h1 className="font-serif text-2xl font-semibold">
                  Uppgifter sparade!
                </h1>
                <p className="text-muted-foreground text-sm">
                  Dina kontuppgifter har uppdaterats.
                </p>
              </div>
            </div>

            {profile && (profile.street_address || profile.postal_code || profile.city) && (
              <div className="mt-4 pt-4 border-t border-border">
                <p className="text-sm font-medium mb-2">Leveransadress:</p>
                <p className="text-muted-foreground text-sm">
                  {profile.street_address && <span>{profile.street_address}<br /></span>}
                  {(profile.postal_code || profile.city) && (
                    <span>{profile.postal_code} {profile.city}</span>
                  )}
                </p>
              </div>
            )}
          </div>

          {/* Subscription status */}
          <div className="bg-card border border-border rounded-lg p-6 md:p-8 shadow-sm mb-6">
            <div className="flex items-center gap-3 mb-4">
              <Package className="h-6 w-6 text-primary" />
              <h2 className="font-serif text-xl font-semibold">Mitt abonnemang</h2>
            </div>

            <div className="bg-muted/50 rounded-lg p-4 mb-6">
              <p className="text-muted-foreground text-sm">
                Du har inget aktivt abonnemang just nu.
              </p>
            </div>

            <Button
              onClick={() => {
                navigate("/");
                setTimeout(() => {
                  const element = document.getElementById("abonnemang");
                  if (element) {
                    element.scrollIntoView({ behavior: "smooth" });
                  }
                }, 100);
              }}
              className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
            >
              Beställ abonnemang
            </Button>
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              variant="outline"
              onClick={() => navigate("/account")}
              className="flex-1"
            >
              Redigera uppgifter
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate("/")}
              className="flex-1"
            >
              Till startsidan
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccountConfirmation;
