import { useState, useMemo } from "react";
import { Loader2 } from "lucide-react";
import { useShopifyProducts } from "@/hooks/useShopifyProducts";
import { useCartStore } from "@/stores/cartStore";
import { toast } from "sonner";

const PRICE_PER_KG = 325;
const KG_PER_EMPLOYEE = 0.3;

// Map recommended kg to the closest available Shopify subscription plan
const availablePlans = [
  { kg: 3, handle: "liten-kakabonnemang-3-kg-vecka", name: "Liten" },
  { kg: 5, handle: "mellan-kakabonnemang-5-kg-vecka", name: "Mellan" },
  { kg: 10, handle: "stor-kakabonnemang-10-kg-vecka", name: "Stor" },
];

const pickPlan = (kg: number) => {
  const match = availablePlans.find((p) => p.kg >= kg);
  return match || availablePlans[availablePlans.length - 1];
};

const PlansSection = () => {
  const [employees, setEmployees] = useState(10);
  const [checkoutLoading, setCheckoutLoading] = useState(false);

  const { products, isLoading: productsLoading } = useShopifyProducts("product_type:Abonnemang");
  const { addItem, clearCart, isLoading: cartLoading } = useCartStore();

  const recommendedKg = useMemo(
    () => Math.max(1, Math.round(employees * KG_PER_EMPLOYEE)),
    [employees]
  );
  const weeklyPrice = recommendedKg * PRICE_PER_KG;

  const handleStart = async () => {
    const plan = pickPlan(recommendedKg);
    const shopifyProduct = products.find((p) => p.node.handle === plan.handle);

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
    try {
      clearCart();
      await addItem({
        product: shopifyProduct,
        variantId: variant.id,
        variantTitle: variant.title,
        price: variant.price,
        quantity: 1,
        selectedOptions: variant.selectedOptions || [],
      });
      toast.success(`Abonnemang tillagt (${plan.name} – ${plan.kg} kg/vecka)`, {
        description: "Klicka på varukorgen för att gå till betalning",
      });
    } catch (e) {
      console.error(e);
      toast.error("Något gick fel");
    } finally {
      setCheckoutLoading(false);
    }
  };

  const isLoading = productsLoading || cartLoading || checkoutLoading;

  return (
    <section id="abonnemang" className="py-16 md:py-28 px-6 bg-background">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10 md:mb-14">
          <div className="w-24 h-px bg-primary/40 mx-auto mb-6"></div>
          <h2 className="font-display text-3xl md:text-5xl font-semibold mb-4">
            Hur många anställda har ni?
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-xl mx-auto">
            Vi rekommenderar automatiskt rätt mängd kakor utifrån antalet medarbetare.
          </p>
        </div>

        {/* Calculator card */}
        <div className="bg-card border border-border rounded-sm shadow-[0_10px_40px_-15px_rgba(0,0,0,0.15)] p-6 md:p-12">
          {/* Employee count display */}
          <div className="text-center mb-8">
            <div
              key={employees}
              className="font-display text-6xl md:text-8xl font-semibold text-primary tabular-nums animate-fade-in"
            >
              {employees}
            </div>
            <div className="text-muted-foreground text-sm md:text-base mt-2 tracking-wide uppercase">
              {employees === 1 ? "anställd" : "anställda"}
            </div>
          </div>

          {/* Slider */}
          <div className="mb-10 md:mb-12">
            <input
              type="range"
              min={1}
              max={100}
              step={1}
              value={employees}
              onChange={(e) => setEmployees(parseInt(e.target.value, 10))}
              className="calculator-slider w-full"
              aria-label="Antal anställda"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-3">
              <span>1</span>
              <span>100</span>
            </div>
          </div>

          {/* Result */}
          <div className="text-center border-t border-border pt-8 md:pt-10 space-y-6">
            <div>
              <div className="text-muted-foreground text-xs md:text-sm uppercase tracking-widest mb-2">
                Rekommenderad mängd
              </div>
              <div className="font-display text-4xl md:text-5xl font-semibold text-foreground tabular-nums">
                {recommendedKg} kg
              </div>
              <div className="text-muted-foreground text-sm mt-1">per vecka</div>
            </div>

            <div>
              <div className="text-muted-foreground text-xs md:text-sm uppercase tracking-widest mb-2">
                Pris per vecka
              </div>
              <div className="font-display text-3xl md:text-4xl font-semibold text-primary tabular-nums">
                {weeklyPrice.toLocaleString("sv-SE")} kr
              </div>
              <div className="text-muted-foreground text-xs mt-1">exklusive moms</div>
            </div>

            <button
              onClick={handleStart}
              disabled={isLoading}
              className="btn-classic w-full py-4 text-base md:text-lg rounded-sm disabled:opacity-50 mt-4"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Laddar...
                </span>
              ) : (
                "Starta abonnemang"
              )}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default PlansSection;
