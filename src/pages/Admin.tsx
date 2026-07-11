import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { AdminStats } from "@/components/admin/AdminStats";
import { OrdersTable } from "@/components/admin/OrdersTable";
import { CustomersTable } from "@/components/admin/CustomersTable";
import { PaymentsTable } from "@/components/admin/PaymentsTable";
import { LeadsGenerator } from "@/components/admin/LeadsGenerator";
import AuthDialog from "@/components/AuthDialog";
import { Package, Users, CreditCard, LogOut, ArrowLeft, Sparkles, Lock } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

type AuthState = "loading" | "signed_out" | "not_admin" | "admin";

export default function Admin() {
  const navigate = useNavigate();
  const [state, setState] = useState<AuthState>("loading");
  const [authOpen, setAuthOpen] = useState(false);

  useEffect(() => {
    const check = async (session: any) => {
      if (!session?.user) {
        setState("signed_out");
        return;
      }
      const { data, error } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", session.user.id)
        .eq("role", "admin")
        .maybeSingle();
      if (error) console.error("Role check failed:", error);
      setState(data ? "admin" : "not_admin");
    };

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, session) => {
      check(session);
    });
    supabase.auth.getSession().then(({ data }) => check(data.session));
    return () => subscription.unsubscribe();
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  if (state === "loading") {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-7xl mx-auto space-y-8">
          <Skeleton className="h-10 w-48" />
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32" />)}
          </div>
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (state === "signed_out") {
    return (
      <>
        <div className="min-h-screen flex items-center justify-center bg-background px-6">
          <div className="max-w-md text-center space-y-6">
            <Lock className="h-12 w-12 mx-auto text-primary" />
            <h1 className="text-3xl font-serif">Admin-inloggning krävs</h1>
            <p className="text-muted-foreground">
              Denna sida är privat. Logga in med ditt admin-konto för att se ordrar och annan intern information.
            </p>
            <div className="flex gap-3 justify-center">
              <Button onClick={() => setAuthOpen(true)}>Logga in</Button>
              <Button variant="outline" onClick={() => navigate("/")}>Till startsidan</Button>
            </div>
          </div>
        </div>
        <AuthDialog open={authOpen} onOpenChange={setAuthOpen} />
      </>
    );
  }

  if (state === "not_admin") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-6">
        <div className="max-w-md text-center space-y-6">
          <Lock className="h-12 w-12 mx-auto text-destructive" />
          <h1 className="text-3xl font-serif">Ingen behörighet</h1>
          <p className="text-muted-foreground">
            Ditt konto har inte tillgång till admin-sidan. Endast ägaren kan se den här sidan.
          </p>
          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={handleLogout}>Logga ut</Button>
            <Button onClick={() => navigate("/")}>Till startsidan</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate("/")}>
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <h1 className="text-2xl font-bold">Admin Dashboard</h1>
            </div>
            <Button variant="outline" onClick={handleLogout}>
              <LogOut className="h-4 w-4 mr-2" />
              Logga ut
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          <AdminStats />

          <Tabs defaultValue="orders" className="space-y-6">
            <TabsList>
              <TabsTrigger value="orders" className="gap-2">
                <Package className="h-4 w-4" />
                Ordrar
              </TabsTrigger>
              <TabsTrigger value="customers" className="gap-2">
                <Users className="h-4 w-4" />
                Kunder
              </TabsTrigger>
              <TabsTrigger value="payments" className="gap-2">
                <CreditCard className="h-4 w-4" />
                Betalningar
              </TabsTrigger>
              <TabsTrigger value="leads" className="gap-2">
                <Sparkles className="h-4 w-4" />
                AI Leads
              </TabsTrigger>
            </TabsList>

            <TabsContent value="orders">
              <OrdersTable />
            </TabsContent>

            <TabsContent value="customers">
              <CustomersTable />
            </TabsContent>

            <TabsContent value="payments">
              <PaymentsTable />
            </TabsContent>

            <TabsContent value="leads">
              <LeadsGenerator />
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
}
