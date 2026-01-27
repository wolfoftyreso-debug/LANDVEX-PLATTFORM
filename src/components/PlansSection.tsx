import { Check } from "lucide-react";

const plans = [
  {
    name: "Kontorsabonnemang Bas",
    price: "1 990 kr",
    period: "/mån",
    description: "Perfekt för mindre kontor (upp till 15 personer)",
    features: [
      "2 leveranser per månad",
      "Premium konditorikakor",
      "Fast leveransdag",
      "Företagsfaktura",
    ],
    featured: false,
  },
  {
    name: "Kontorsabonnemang Pro",
    price: "3 490 kr",
    period: "/mån",
    description: "För växande företag (15–40 personer)",
    features: [
      "4 leveranser per månad",
      "Utvalda sortiment",
      "Prioriterad hantering",
      "Fakturabetalning",
    ],
    featured: true,
  },
  {
    name: "Företagsavtal",
    price: "Offert",
    period: "",
    description: "För stora kontor, event och kedjor",
    features: [
      "Anpassad volym",
      "Möjlighet till branding",
      "Avtalspriser",
      "Personlig kontakt",
    ],
    featured: false,
  },
];

const PlansSection = () => {
  return (
    <section id="plans" className="py-24 px-6 bg-secondary/50">
      <div className="max-w-6xl mx-auto">
        <h2 className="font-display text-center text-4xl md:text-5xl font-bold mb-4">
          Våra företagsabonnemang
        </h2>
        <p className="text-center text-muted-foreground mb-16 max-w-2xl mx-auto">
          Välj det abonnemang som passar ert företag bäst
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`relative rounded-3xl p-8 flex flex-col card-glow ${
                plan.featured
                  ? "bg-gradient-to-b from-primary/20 to-card border-2 border-primary/30"
                  : "bg-card border border-border"
              }`}
            >
              {plan.featured && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="btn-primary px-4 py-1.5 text-sm rounded-full">
                    Mest populär
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="font-display text-2xl font-bold mb-2">
                  {plan.name}
                </h3>
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold text-gradient">
                    {plan.price}
                  </span>
                  <span className="text-muted-foreground">{plan.period}</span>
                </div>
              </div>

              <p className="text-muted-foreground mb-8">{plan.description}</p>

              <ul className="space-y-4 mb-8 flex-grow">
                {plan.features.map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                      <Check className="w-3 h-3 text-primary" />
                    </div>
                    <span className="text-foreground/80">{feature}</span>
                  </li>
                ))}
              </ul>

              <a
                href="#"
                className={`text-center py-4 rounded-xl font-semibold transition-all duration-300 ${
                  plan.featured
                    ? "btn-primary"
                    : "bg-secondary hover:bg-secondary/80 text-foreground border border-border"
                }`}
              >
                {plan.price === "Offert" ? "Kontakta oss" : "Starta abonnemang"}
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default PlansSection;
