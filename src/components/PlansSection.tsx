import { Check } from "lucide-react";

const plans = [
  {
    name: "Bas",
    subtitle: "Kontorsabonnemang",
    price: "1 990",
    period: "kr/månad",
    description: "Perfekt för mindre kontor med upp till 15 personer",
    features: [
      "2 leveranser per månad",
      "Premium konditorikakor",
      "Fast leveransdag",
      "Företagsfaktura",
    ],
    featured: false,
  },
  {
    name: "Pro",
    subtitle: "Kontorsabonnemang",
    price: "3 490",
    period: "kr/månad",
    description: "För växande företag med 15–40 personer",
    features: [
      "4 leveranser per månad",
      "Utvalda sortiment",
      "Prioriterad hantering",
      "Fakturabetalning",
    ],
    featured: true,
  },
  {
    name: "Avtal",
    subtitle: "Företagsanpassat",
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

              {/* Price */}
              <div className="text-center mb-6">
                <span className="font-display text-4xl font-bold text-primary">
                  {plan.price}
                </span>
                {plan.period && (
                  <span className="text-muted-foreground ml-1">{plan.period}</span>
                )}
              </div>

              <p className="text-muted-foreground text-center mb-8 text-sm">
                {plan.description}
              </p>

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
                {plan.price === "Offert" ? "Begär offert" : "Välj abonnemang"}
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
