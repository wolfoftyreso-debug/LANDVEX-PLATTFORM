import { useState, useMemo } from "react";
import { Loader2, CreditCard, FileText } from "lucide-react";
import {
  storefrontApiRequest,
  CART_CREATE_MUTATION,
  formatCheckoutUrl,
} from "@/lib/shopify";
import { toast } from "sonner";

const PRICE_PER_KG = 325;
const KG_PER_EMPLOYEE = 0.3;

const availablePlans = [
  { kg: 3, handle: "liten-kakabonnemang-3-kg-vecka", name: "Liten" },
  { kg: 5, handle: "mellan-kakabonnemang-5-kg-vecka", name: "Mellan" },
  { kg: 10, handle: "stor-kakabonnemang-10-kg-vecka", name: "Stor" },
];

const pickPlan = (kg: number) => {
  const match = availablePlans.find((p) => p.kg >= kg);
  return match || availablePlans[availablePlans.length - 1];
};

const PRODUCT_BY_HANDLE_QUERY = `
  query ProductByHandle($handle: String!) {
    productByHandle(handle: $handle) {
      id
      title
      handle
      variants(first: 1) {
        edges {
          node {
            id
            availableForSale
          }
        }
      }
      sellingPlanGroups(first: 5) {
        edges {
          node {
            name
            sellingPlans(first: 10) {
              edges {
                node {
                  id
                  name
                }
              }
            }
          }
        }
      }
    }
  }
`;

type PaymentMethod = "card" | "invoice";

const PlansSection = () => {
  const [employees, setEmployees] = useState(10);
  const [loadingMethod, setLoadingMethod] = useState<PaymentMethod | null>(null);
  const [showPaymentOptions, setShowPaymentOptions] = useState(false);

  const recommendedKg = useMemo(
    () => Math.max(1, Math.round(employees * KG_PER_EMPLOYEE)),
    [employees]
  );
  const weeklyPrice = recommendedKg * PRICE_PER_KG;

  const handleStart = async (method: PaymentMethod) => {
    const plan = pickPlan(recommendedKg);
    setLoadingMethod(method);

    try {
      const productData = await storefrontApiRequest(PRODUCT_BY_HANDLE_QUERY, {
        handle: plan.handle,
      });

      const product = productData?.data?.productByHandle;
      if (!product) {
        toast.error(`Kunde inte hitta produkten "${plan.handle}" i Shopify.`);
        return;
      }

      const variant = product.variants?.edges?.[0]?.node;
      if (!variant?.id) {
        toast.error("Ingen variant tillgänglig på produkten.");
        return;
      }

      const sellingPlanId =
        product.sellingPlanGroups?.edges?.[0]?.node?.sellingPlans?.edges?.[0]?.node?.id;

      if (!sellingPlanId) {
        toast.error(
          "Ingen Appstle-abonnemangsplan hittades. Aktivera Storefront-behörigheten 'unauthenticated_read_selling_plans' och koppla en Appstle-plan till produkten.",
          { duration: 10000 }
        );
        return;
      }

      const data = await storefrontApiRequest(CART_CREATE_MUTATION, {
        input: {
          lines: [
            {
              quantity: 1,
              merchandiseId: variant.id,
              sellingPlanId,
            },
          ],
          attributes: [
            { key: "Antal anställda", value: String(employees) },
            { key: "Rekommenderad mängd", value: `${recommendedKg} kg/vecka` },
            { key: "Veckopris (exkl. moms)", value: `${weeklyPrice} kr` },
            {
              key: "Önskad betalningsmetod",
              value: method === "card" ? "Automatiskt kort varje månad" : "Månadsfaktura",
            },
          ],
        },
      });

      const errors = data?.data?.cartCreate?.userErrors || [];
      if (errors.length > 0) {
        console.error("Cart creation failed:", errors);
        toast.error("Kunde inte skapa checkout: " + errors[0].message);
        return;
      }

      const checkoutUrl = data?.data?.cartCreate?.cart?.checkoutUrl;
      if (!checkoutUrl) {
        toast.error("Ingen checkout-länk mottagen");
        return;
      }

      window.open(formatCheckoutUrl(checkoutUrl), "_blank");
    } catch (e) {
      console.error(e);
      toast.error("Något gick fel vid checkout");
    } finally {
      setLoadingMethod(null);
    }
  };


  const isBusy = productsLoading || loadingMethod !== null;

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

            {!showPaymentOptions ? (
              <button
                onClick={() => setShowPaymentOptions(true)}
                disabled={isBusy}
                className="btn-classic w-full py-4 text-base md:text-lg rounded-sm disabled:opacity-50 mt-2"
              >
                Starta abonnemang
              </button>
            ) : (
              <div className="animate-fade-in space-y-3 pt-2">
                <p className="text-muted-foreground text-sm">
                  Välj betalningsmetod
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    onClick={() => handleStart("card")}
                    disabled={isBusy}
                    className="btn-classic py-4 px-4 text-base rounded-sm disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loadingMethod === "card" ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <CreditCard className="w-5 h-5" />
                        <span>Automatiskt varje månad</span>
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => handleStart("invoice")}
                    disabled={isBusy}
                    className="py-4 px-4 text-base rounded-sm border-2 border-primary text-primary hover:bg-primary hover:text-primary-foreground transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loadingMethod === "invoice" ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <FileText className="w-5 h-5" />
                        <span>Månadsfaktura</span>
                      </>
                    )}
                  </button>
                </div>
                <button
                  onClick={() => setShowPaymentOptions(false)}
                  className="text-muted-foreground text-xs underline hover:text-foreground"
                >
                  ← Tillbaka
                </button>
                <p className="text-muted-foreground text-xs">
                  Du slutför beställningen säkert hos Shopify.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};

export default PlansSection;
