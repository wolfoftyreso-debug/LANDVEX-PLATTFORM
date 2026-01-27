import { Check } from "lucide-react";

const plans = [
  {
    name: "Starter",
    subtitle: "Abonnemang",
    kgPerWeek: "3 kg",
    priceWeekExclVat: "1 350",
    priceWeekInclVat: "1 687,50",
    priceMonthExclVat: "5 400",
    priceMonthInclVat: "6 750",
    features: [
      "3 kg kakor per vecka",
      "Veckoleverans",
      "Företagsfaktura",
      "Flexibelt upplägg",
    ],
    featured: false,
  },
  {
    name: "Standard",
    subtitle: "Abonnemang",
    kgPerWeek: "5 kg",
    priceWeekExclVat: "2 250",
    priceWeekInclVat: "2 812,50",
    priceMonthExclVat: "9 000",
    priceMonthInclVat: "11 250",
    features: [
      "5 kg kakor per vecka",
      "Veckoleverans",
      "Prioriterad hantering",
      "Företagsfaktura",
    ],
    featured: true,
  },
  {
    name: "Pro / Office Plus",
    subtitle: "Abonnemang",
    kgPerWeek: "10 kg",
    priceWeekExclVat: "4 500",
    priceWeekInclVat: "5 625",
    priceMonthExclVat: "18 000",
    priceMonthInclVat: "22 500",
    features: [
      "10 kg kakor per vecka",
      "Veckoleverans",
      "Personlig kontakt",
      "Anpassade sortiment",
    ],
    featured: false,
  },
];

const PlansSection = () => {
  return (
    <section id="plans" className="py-24 px-6 bg-background">
      <div className="max-w-5xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16">
          <div className="divider-ornament mb-6">
            <span className="ornament">✦</span>
          </div>
          <h2 className="font-display text-4xl md:text-5xl font-semibold mb-4 italic">
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
              className={`relative bg-card p-8 card-classic rounded-sm ${
                plan.featured ? "border-2 border-primary" : ""
              }`}
            >
              {plan.featured && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-primary text-primary-foreground px-4 py-1 text-sm font-semibold rounded-sm">
                    Rekommenderad
                  </span>
                </div>
              )}

              {/* Plan header */}
              <div className="text-center mb-6 pb-6 border-b border-border">
                <p className="text-muted-foreground text-sm uppercase tracking-wider mb-1">
                  {plan.subtitle}
                </p>
                <h3 className="font-display text-3xl font-semibold text-foreground italic">
                  {plan.name}
                </h3>
              </div>

              {/* Price info */}
              <div className="text-center mb-6 space-y-2">
                <div className="text-muted-foreground text-sm">
                  {plan.kgPerWeek}/vecka
                </div>
                <div>
                  <span className="font-display text-3xl font-bold text-primary">
                    {plan.priceMonthInclVat}
                  </span>
                  <span className="text-muted-foreground ml-1">kr/mån</span>
                </div>
                <div className="text-muted-foreground text-xs">
                  ({plan.priceMonthExclVat} kr exkl. moms)
                </div>
                <div className="text-muted-foreground text-xs border-t border-border pt-2 mt-2">
                  Veckopris: {plan.priceWeekInclVat} kr inkl. moms
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
              <a
                href="#"
                className={`block text-center py-3 px-6 rounded-sm font-semibold transition-all duration-300 ${
                  plan.featured
                    ? "btn-classic"
                    : "btn-outline-classic"
                }`}
              >
                Välj abonnemang
              </a>
            </div>
          ))}
        </div>

        {/* Bottom ornament */}
        <div className="text-center mt-16 text-primary/40 font-display text-2xl">
          ❦
        </div>
      </div>
    </section>
  );
};

export default PlansSection;
