import { useSearchParams, useNavigate } from "react-router-dom";
import { CheckCircle2, Truck, Mail, Calendar } from "lucide-react";
import Header from "@/components/Header";
import { Button } from "@/components/ui/button";

const OrderConfirmation = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const method = searchParams.get("method") ?? "card";
  const kg = searchParams.get("kg");
  const email = searchParams.get("email");
  const sessionId = searchParams.get("session_id");

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="pt-28 md:pt-32 px-6 pb-20">
        <div className="max-w-2xl mx-auto">
          <div className="text-center mb-10 animate-fade-in">
            <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
              <CheckCircle2 className="w-11 h-11 text-primary" strokeWidth={1.5} />
            </div>
            <div className="w-24 h-px bg-primary/40 mx-auto mb-6" />
            <h1 className="font-display text-4xl md:text-5xl font-semibold mb-4">
              Tack för din beställning!
            </h1>
            <p className="font-display italic text-lg md:text-xl text-muted-foreground">
              Goda saker är på väg.
            </p>
          </div>

          <div className="bg-card border border-border rounded-sm shadow-[0_10px_40px_-15px_rgba(0,0,0,0.15)] p-6 md:p-10 space-y-6">
            {kg && (
              <div className="text-center pb-6 border-b border-border">
                <div className="text-muted-foreground text-xs uppercase tracking-widest mb-2">
                  Ditt abonnemang
                </div>
                <div className="font-display text-3xl md:text-4xl font-semibold text-primary tabular-nums">
                  {kg} kg kakor / vecka
                </div>
              </div>
            )}

            <div className="flex items-start gap-4">
              <Truck className="w-6 h-6 text-primary flex-shrink-0 mt-0.5" strokeWidth={1.5} />
              <div>
                <div className="font-display text-lg font-semibold mb-1">Leverans varje tisdag</div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Vi levererar färska kakor till er adress inom Storstockholm varje tisdag
                  morgon. Första leveransen kommer inom kort.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Calendar className="w-6 h-6 text-primary flex-shrink-0 mt-0.5" strokeWidth={1.5} />
              <div>
                <div className="font-display text-lg font-semibold mb-1">
                  {method === "invoice" ? "Faktura varje månad" : "Månatlig kortdragning"}
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {method === "invoice"
                    ? "Faktura skickas till er e-post varje månad med 30 dagars betalningsvillkor."
                    : "Beloppet dras automatiskt från ert kort en gång i månaden. Du kan säga upp när som helst."}
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <Mail className="w-6 h-6 text-primary flex-shrink-0 mt-0.5" strokeWidth={1.5} />
              <div>
                <div className="font-display text-lg font-semibold mb-1">Orderbekräftelse</div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  En bekräftelse{email ? <> skickas till <strong className="text-foreground">{email}</strong></> : " skickas till din e-post"} inom kort.
                </p>
              </div>
            </div>

            {sessionId && (
              <div className="pt-4 border-t border-border text-center">
                <p className="text-xs text-muted-foreground font-mono break-all">
                  Referens: {sessionId}
                </p>
              </div>
            )}
          </div>

          <div className="text-center mt-10">
            <Button
              onClick={() => navigate("/")}
              variant="outline"
              className="font-display"
            >
              Tillbaka till startsidan
            </Button>
          </div>

          <p className="text-center text-sm text-muted-foreground mt-8 italic font-display">
            Äkta svenskt konditorhantverk
          </p>
        </div>
      </main>
    </div>
  );
};

export default OrderConfirmation;
