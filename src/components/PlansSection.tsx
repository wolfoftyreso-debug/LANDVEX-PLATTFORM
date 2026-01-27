import { useState, useEffect } from "react";
import { Check, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
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
    shopifyHandle: "stor-kakabonnemang-10-kg-vecka",
  },
];

const PlansSection = () => {
  const [selectedPlan, setSelectedPlan] = useState<string>("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  
  const { products, isLoading: productsLoading } = useShopifyProducts("product_type:Abonnemang");
  const { addItem, getCheckoutUrl, isLoading: cartLoading } = useCartStore();

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
      await addItem({
        product: shopifyProduct,
        variantId: variant.id,
        variantTitle: variant.title,
        price: variant.price,
        quantity: 1,
        selectedOptions: variant.selectedOptions || [],
      });

      // Small delay to ensure cart is created
      await new Promise(resolve => setTimeout(resolve, 500));

      const checkoutUrl = useCartStore.getState().getCheckoutUrl();
      if (checkoutUrl) {
        window.open(checkoutUrl, '_blank');
        toast.success("Omdirigerar till betalning...");
      } else {
        toast.error("Kunde inte skapa checkout");
      }
    } catch (error) {
      console.error('Checkout error:', error);
      toast.error("Något gick fel");
    } finally {
      setCheckoutLoading(false);
    }
  };

  const isLoading = productsLoading || cartLoading || checkoutLoading;

  return (
    <section id="abonnemang" className="py-24 px-6 bg-background">
      <div className="max-w-5xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16">
          <div className="w-24 h-px bg-primary/40 mx-auto mb-6"></div>
          <h2 className="font-display text-4xl md:text-5xl font-semibold mb-4">
            Våra Abonnemang
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Välj det abonnemang som passar ert företag bäst
          </p>
        </div>

        {/* Plans grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {planDetails.map((plan, index) => (
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
                disabled={isLoading}
                className="block w-full text-center py-3 px-6 rounded-sm font-semibold transition-all duration-300 btn-classic disabled:opacity-50"
              >
                {isLoading && selectedPlan === plan.name ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Laddar...
                  </span>
                ) : (
                  "Beställ nu"
                )}
              </button>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
};

export default PlansSection;
