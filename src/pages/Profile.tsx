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

const profileSchema = z.object({
  display_name: z.string().trim().max(100, { message: "Namn får max vara 100 tecken" }).optional(),
  phone: z.string().trim().max(20, { message: "Telefonnummer får max vara 20 tecken" }).optional(),
  address: z.string().trim().max(500, { message: "Adress får max vara 500 tecken" }).optional(),
});

interface ProfileData {
  display_name: string;
  phone: string;
  address: string;
}

const Profile = () => {
  const [profile, setProfile] = useState<ProfileData>({
    display_name: "",
    phone: "",
    address: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const { user, loading: authLoading } = useAuth();
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
        .select("display_name, phone, address")
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
          display_name: data.display_name || "",
          phone: data.phone || "",
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
          display_name: profile.display_name || null,
          phone: profile.phone || null,
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
        toast({
          title: "Profil sparad!",
          description: "Dina uppgifter har uppdaterats.",
        });
      }
    } finally {
      setIsSaving(false);
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
        <div className="max-w-lg mx-auto">
          <div className="bg-card border border-border rounded-lg p-8 shadow-sm">
            <h1 className="font-serif text-2xl text-center mb-2">Min profil</h1>
            <p className="text-muted-foreground text-center text-sm mb-6">
              {user?.email}
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="display_name">Namn</Label>
                <Input
                  id="display_name"
                  type="text"
                  value={profile.display_name}
                  onChange={(e) =>
                    setProfile({ ...profile, display_name: e.target.value })
                  }
                  placeholder="Ditt namn"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone">Telefon</Label>
                <Input
                  id="phone"
                  type="tel"
                  value={profile.phone}
                  onChange={(e) =>
                    setProfile({ ...profile, phone: e.target.value })
                  }
                  placeholder="070-123 45 67"
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
              </div>

              <Button
                type="submit"
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                disabled={isSaving}
              >
                {isSaving ? "Sparar..." : "Spara ändringar"}
              </Button>
            </form>

            <div className="text-center mt-6">
              <button
                type="button"
                onClick={() => navigate("/")}
                className="text-sm text-primary hover:underline"
              >
                Tillbaka till startsidan
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile;
