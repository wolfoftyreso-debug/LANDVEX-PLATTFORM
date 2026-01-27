import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { CheckCircle } from "lucide-react";
import Header from "@/components/Header";

const AccountConfirmation = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <div className="pt-24 px-4 pb-12">
        <div className="max-w-lg mx-auto text-center">
          <div className="bg-card border border-border rounded-lg p-8 md:p-12 shadow-sm">
            <div className="flex justify-center mb-6">
              <CheckCircle className="h-16 w-16 text-primary" />
            </div>
            
            <h1 className="font-serif text-2xl md:text-3xl font-semibold mb-4">
              Uppgifter sparade!
            </h1>
            
            <p className="text-muted-foreground mb-8">
              Dina kontuppgifter har sparats. Du kan nu beställa abonnemang med dessa uppgifter.
            </p>

            <div className="space-y-3">
              <Button
                onClick={() => navigate("/")}
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
              >
                Tillbaka till startsidan
              </Button>
              
              <Button
                variant="outline"
                onClick={() => navigate("/account")}
                className="w-full"
              >
                Redigera uppgifter
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccountConfirmation;
