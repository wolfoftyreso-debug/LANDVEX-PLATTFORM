interface Plan {
  kg: number;
  pricePerKg: number;
  shopifyLink: string;
}

interface AbonnemangCheckoutProps {
  selectedPlan: string;
  onBack?: () => void;
}

const plans: Record<string, Plan> = {
  "Liten": { 
    kg: 3, 
    pricePerKg: 450, 
    shopifyLink: "#" // Replace with actual Shopify link
  },
  "Mellan": { 
    kg: 5, 
    pricePerKg: 450, 
    shopifyLink: "#" 
  },
  "Stor": { 
    kg: 10, 
    pricePerKg: 400, 
    shopifyLink: "#" 
  },
};

const AbonnemangCheckout = ({ selectedPlan, onBack }: AbonnemangCheckoutProps) => {
  const planName = selectedPlan.split(" (")[0]; // Extract plan name from "Liten (3 kg/vecka)"
  const plan = plans[planName] || plans["Mellan"];
  const weeklyPrice = plan.kg * plan.pricePerKg;
  const monthlyPrice = weeklyPrice * 4;

  return (
    <div className="text-center py-8">
      <div className="w-24 h-px bg-primary/40 mx-auto mb-6"></div>
      
      <h2 className="font-display text-3xl md:text-4xl font-semibold mb-4">
        Ditt abonnemang: {planName}
      </h2>
      
      <div className="text-muted-foreground mb-6 space-y-2">
        <p>
          Du beställer <strong className="text-foreground">{plan.kg} kg</strong> kakor per vecka.
        </p>
        <p>
          Pris: <strong className="text-foreground">{weeklyPrice.toLocaleString("sv-SE")} kr/vecka</strong>{" "}
          <span className="text-sm">(~{monthlyPrice.toLocaleString("sv-SE")} kr/månad exkl. moms)</span>
        </p>
        <p className="text-primary font-semibold mt-4">
          Kakorna levereras nästa tisdag!
        </p>
      </div>

      <p className="text-muted-foreground text-sm mb-8">
        Betala direkt via kort eller med Klarna. Ingen manuell kontakt behövs.
      </p>

      <div className="flex flex-col sm:flex-row gap-4 justify-center mb-8">
        <a
          href={plan.shopifyLink}
          className="btn-classic px-8 py-4 text-center"
        >
          Betala med kort
        </a>
        <a
          href={plan.shopifyLink + "?payment=klarna"}
          className="btn-outline-classic px-8 py-4 text-center"
        >
          Betala med Klarna
        </a>
      </div>

      <p className="text-muted-foreground text-sm">
        När betalningen är genomförd skickas automatiskt ett bekräftelsemail
        och kakorna levereras nästa tisdag.
      </p>

      {onBack && (
        <button
          onClick={onBack}
          className="mt-6 text-primary underline hover:no-underline"
        >
          ← Tillbaka till formulär
        </button>
      )}
    </div>
  );
};

export default AbonnemangCheckout;
