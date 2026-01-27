import { useState } from "react";
import { Check } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import AbonnemangForm from "./AbonnemangForm";

const plans = [
  {
    name: "Liten",
    kgPerWeek: "3 kg",
    priceWeekExclVat: "1 350",
    employeeRecommendation: "1–10 anställda",
    features: [
      "3 kg kakor per vecka",
      "Veckoleverans",
      "Betala direkt eller med Klarna",
    ],
  },
  {
    name: "Mellan",
    kgPerWeek: "5 kg",
    priceWeekExclVat: "2 250",
    employeeRecommendation: "10–25 anställda",
    features: [
      "5 kg kakor per vecka",
      "Veckoleverans",
      "Betala direkt eller med Klarna",
    ],
  },
  {
    name: "Stor",
    kgPerWeek: "10 kg",
    priceWeekExclVat: "4 500",
    employeeRecommendation: "25+ anställda",
    features: [
      "10 kg kakor per vecka",
      "Veckoleverans",
      "Betala direkt eller med Klarna",
    ],
  },
];

const PlansSection = () => {
  const [selectedPlan, setSelectedPlan] = useState<string>("");
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleSelectPlan = (plan: typeof plans[0]) => {
    setSelectedPlan(`${plan.name} (${plan.kgPerWeek}/vecka)`);
    setDialogOpen(true);
  };

  return (
    <section id="plans" className="py-24 px-6 bg-background">
      <div className="max-w-5xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16">
          <div className="divider-ornament mb-6">
            <span className="ornament">✦</span>
          </div>
          <h2 className="font-display text-4xl md:text-5xl font-semibold mb-4">
            Våra Abonnemang
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Välj det abonnemang som passar ert företag bäst
          </p>
        </div>

        {/* Plans grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {plans.map((plan, index) => (
            <div
              key={index}
              className="relative bg-card p-8 card-classic rounded-sm"
            >
              {/* Plan header */}
              <div className="text-center mb-6 pb-6 border-b border-border">
                <h3 className="font-display text-3xl font-semibold text-foreground">
                  {plan.name}
                </h3>
                <p className="text-muted-foreground text-sm mt-2">
                  Rekommenderas för {plan.employeeRecommendation}
                </p>
              </div>

              {/* Price info */}
              <div className="text-center mb-6 space-y-2">
                <div className="text-muted-foreground text-sm">
                  {plan.kgPerWeek}/vecka
                </div>
                <div>
                  <span className="font-display text-3xl font-bold text-primary">
                    {plan.priceWeekExclVat}
                  </span>
                  <span className="text-muted-foreground ml-1">kr/vecka exkl. moms</span>
                </div>
              </div>

              {/* Features */}
              <ul className="space-y-3 mb-8">
                {plan.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <Check className="w-4 h-4 text-primary mt-1 flex-shrink-0" />
                    <span className="text-foreground/80 text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              {/* CTA Button */}
              <button
                onClick={() => handleSelectPlan(plan)}
                className="block w-full text-center py-3 px-6 rounded-sm font-semibold transition-all duration-300 btn-classic"
              >
                Välj abonnemang
              </button>
            </div>
          ))}
        </div>

        {/* Bottom ornament */}
        <div className="text-center mt-16 text-primary/40 font-display text-2xl">
          ❦
        </div>
      </div>

      {/* Order Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto bg-card">
          <AbonnemangForm
            selectedPlan={selectedPlan}
            onClose={() => setDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </section>
  );
};

export default PlansSection;
