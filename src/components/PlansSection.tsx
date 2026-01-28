import { useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { useShopifyProducts } from "@/hooks/useShopifyProducts";
import { useCartStore } from "@/stores/cartStore";
import { toast } from "sonner";

const planDetails = [
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
    shopifyHandle: "liten-kakabonnemang-3-kg-vecka",
    isPremium: false,
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
    shopifyHandle: "mellan-kakabonnemang-5-kg-vecka",
    isPremium: false,
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
      "Prioriterad leverans",
    ],
    shopifyHandle: "stor-kakabonnemang-10-kg-vecka",
    isPremium: true,
  },
];

const PlansSection = () => {
  const [selectedPlan, setSelectedPlan] = useState<string>("");
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  
  const { products, isLoading: productsLoading } = useShopifyProducts("product_type:Abonnemang");
  const { addItem, clearCart, isLoading: cartLoading } = useCartStore();

  const handleSelectPlan = async (plan: typeof planDetails[0]) => {
    // Find the matching Shopify product
    const shopifyProduct = products.find(p => p.node.handle === plan.shopifyHandle);
    
    if (!shopifyProduct) {
      toast.error("Kunde inte hitta produkten");
      return;
    }

    const variant = shopifyProduct.node.variants.edges[0]?.node;
    if (!variant) {
      toast.error("Ingen variant tillgänglig");
      return;
    }

    setCheckoutLoading(true);
    setSelectedPlan(plan.name);

    try {
      // Clear any existing cart items first for a clean order
      clearCart();

      await addItem({
        product: shopifyProduct,
        variantId: variant.id,
        variantTitle: variant.title,
        price: variant.price,
        quantity: 1,
        selectedOptions: variant.selectedOptions || [],
      });

      toast.success(`${plan.name} tillagt i varukorgen`, {
        description: "Klicka på varukorgen för att gå till betalning",
      });
    } catch (error) {
      console.error('Add to cart error:', error);
      toast.error("Något gick fel");
    } finally {
      setCheckoutLoading(false);
    }
  };

  const isLoading = productsLoading || cartLoading || checkoutLoading;

  return (
    <section id="abonnemang" className="py-12 md:py-24 px-2 md:px-6 bg-background">
      <div className="max-w-5xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-8 md:mb-16">
          <div className="w-16 md:w-24 h-px bg-primary/40 mx-auto mb-4 md:mb-6"></div>
          <h2 className="font-display text-2xl md:text-5xl font-semibold mb-2 md:mb-4">
            Våra Abonnemang
          </h2>
          <p className="text-muted-foreground text-sm md:text-lg max-w-2xl mx-auto">
            Välj det abonnemang som passar ert företag bäst
          </p>
        </div>

        {/* Plans grid */}
        <div className="grid grid-cols-3 gap-4 md:gap-8">
          {planDetails.map((plan, index) => (
            <div
              key={index}
              className={`relative bg-card p-3 md:p-8 card-classic rounded-sm flex flex-col ${
                plan.isPremium 
                  ? 'ring-2 ring-amber-500 hover:ring-2 hover:ring-amber-500 shadow-[0_0_20px_rgba(217,164,32,0.3)] hover:shadow-[0_0_30px_rgba(217,164,32,0.4)]' 
                  : ''
              }`}
            >

              {/* Plan header */}
              <div className={`text-center mb-3 md:mb-6 pb-3 md:pb-6 border-b ${plan.isPremium ? 'border-amber-400/50' : 'border-border'}`}>
                <h3 className={`font-display text-base md:text-3xl font-semibold ${plan.isPremium ? 'text-amber-700' : 'text-foreground'}`}>
                  {plan.name}
                </h3>
                <p className="text-muted-foreground text-[10px] md:text-sm mt-1 md:mt-2 leading-tight">
                  {plan.employeeRecommendation}
                </p>
              </div>

              {/* Price info */}
              <div className="text-center mb-3 md:mb-6 space-y-1 md:space-y-2">
                <div className="text-muted-foreground text-[10px] md:text-sm">
                  {plan.kgPerWeek}/vecka
                </div>
                <div>
                  <span className="font-display text-sm md:text-3xl font-bold text-primary">
                    {plan.priceWeekExclVat}
                  </span>
                  <span className="text-muted-foreground text-[8px] md:text-base ml-0.5 md:ml-1">kr/v</span>
                </div>
              </div>

              {/* Features - hidden on mobile */}
              <ul className="hidden md:block space-y-3 mb-8 flex-grow">
                {plan.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <Check className="w-4 h-4 text-primary mt-1 flex-shrink-0" />
                    <span className="text-foreground/80 text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              {/* CTA Button - always at bottom */}
              <button
                onClick={() => handleSelectPlan(plan)}
                disabled={isLoading}
                className="block w-full text-center py-1.5 md:py-3 px-2 md:px-6 rounded-sm text-[10px] md:text-base font-semibold transition-all duration-300 btn-classic disabled:opacity-50"
              >
                {isLoading && selectedPlan === plan.name ? (
                  <span className="flex items-center justify-center gap-1 md:gap-2">
                    <Loader2 className="w-3 h-3 md:w-4 md:h-4 animate-spin" />
                    <span className="hidden md:inline">Laddar...</span>
                  </span>
                ) : (
                  "Beställ"
                )}
              </button>
            </div>
          ))}
        </div>

        {/* Satisfaction guarantee */}
        <div className="mt-8 md:mt-12 text-center">
          <p className="font-display text-sm md:text-xl italic text-muted-foreground">
            Alltid med fullständig nöjdhetsgaranti
          </p>
        </div>

      </div>
    </section>
  );
};

export default PlansSection;
