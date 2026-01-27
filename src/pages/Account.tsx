import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import Header from "@/components/Header";
import { LogOut, Save } from "lucide-react";

const profileSchema = z.object({
  address: z.string().trim().max(500, { message: "Adress får max vara 500 tecken" }).optional(),
});

interface ProfileData {
  address: string;
}

const Account = () => {
  const [profile, setProfile] = useState<ProfileData>({
    address: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const { user, loading: authLoading, signOut } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();

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
      const { data, error } = await supabase
        .from("profiles")
        .select("address")
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
        setProfile({
          address: data.address || "",
        });
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
          address: profile.address || null,
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
        navigate("/account/confirmation");
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
                <Label htmlFor="address">Leveransadress</Label>
                <Textarea
                  id="address"
                  value={profile.address}
                  onChange={(e) =>
                    setProfile({ ...profile, address: e.target.value })
                  }
                  placeholder="Gatuadress, postnummer, ort"
                  rows={3}
                />
                <p className="text-xs text-muted-foreground">
                  Denna adress används vid beställning av abonnemang.
                </p>
              </div>

              <Button
                type="submit"
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                disabled={isSaving}
              >
                <Save className="h-4 w-4 mr-2" />
                {isSaving ? "Sparar..." : "Spara ändringar"}
              </Button>
            </form>
          </div>

          {/* Sign Out */}
          <div className="bg-card border border-border rounded-lg p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium">Logga ut</h3>
                <p className="text-sm text-muted-foreground">
                  Logga ut från ditt konto
                </p>
              </div>
              <Button
                variant="outline"
                onClick={handleSignOut}
                className="border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground"
              >
                <LogOut className="h-4 w-4 mr-2" />
                Logga ut
              </Button>
            </div>
          </div>

          {/* Back link */}
          <div className="text-center mt-8">
            <button
              type="button"
              onClick={() => navigate("/")}
              className="text-sm text-primary hover:underline"
            >
              ← Tillbaka till startsidan
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Account;
