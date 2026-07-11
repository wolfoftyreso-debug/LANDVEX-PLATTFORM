import { useState, useEffect } from "react";
import { z } from "zod";
import { useAuth } from "@/hooks/useAuth";
import { supabase } from "@/integrations/supabase/client";

// Validate Stockholm postal codes (100 00 - 199 99)
const isStockholmPostalCode = (postalCode: string) => {
  const cleaned = postalCode.replace(/\s/g, "");
  if (!/^\d{5}$/.test(cleaned)) return false;
  const num = parseInt(cleaned, 10);
  return num >= 10000 && num <= 19999;
};

// Get error message for postal code (for real-time validation display)
const getPostalCodeError = (postalCode: string) => {
  if (!postalCode || postalCode.trim() === "") return null;
  const cleaned = postalCode.replace(/\s/g, "");
  if (cleaned.length < 5) return null; // Don't show error while typing
  if (!/^\d{5}$/.test(cleaned)) return "Ange ett giltigt postnummer (5 siffror)";
  const num = parseInt(cleaned, 10);
  if (num < 10000 || num > 19999) {
    return "Vi levererar endast inom Storstockholm (100 00 – 199 99)";
  }
  return null;
};

const formSchema = z.object({
  företag: z.string().trim().min(1, "Fyll i företagsnamn").max(100),
  epost: z.string().trim().email("Ange en giltig e-postadress").max(255),
  telefon: z.string().trim().max(20).optional(),
  adress: z.string().trim().max(200).optional(),
  postnummer: z
    .string()
    .trim()
    .min(1, "Fyll i postnummer för leverans")
    .max(10)
    .refine(
      (val) => isStockholmPostalCode(val),
      { message: "Vi levererar endast inom Storstockholm (100 00 – 199 99)" }
    ),
  stad: z.string().trim().max(100).optional(),
  abonnemang: z.string().min(1, "Välj ett abonnemang"),
  kommentarer: z.string().trim().max(1000).optional(),
});

interface AbonnemangFormProps {
  selectedPlan?: string;
  onClose?: () => void;
}

const AbonnemangForm = ({ selectedPlan, onClose }: AbonnemangFormProps) => {
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    företag: "",
    epost: "",
    telefon: "",
    adress: "",
    postnummer: "",
    stad: "",
    abonnemang: selectedPlan || "",
    kommentarer: "",
  });

  const [submitted, setSubmitted] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Pre-fill form with user's profile data if logged in
  useEffect(() => {
    const fetchProfileData = async () => {
      if (user) {
        const { data } = await supabase
          .from("profiles")
          .select("display_name, phone, address")
          .eq("user_id", user.id)
          .maybeSingle();

        if (data) {
          setFormData((prev) => ({
            ...prev,
            telefon: data.phone || prev.telefon,
            epost: user.email || prev.epost,
            adress: data.address?.split(",")[0]?.trim() || prev.adress,
          }));
        } else {
          setFormData((prev) => ({
            ...prev,
            epost: user.email || prev.epost,
          }));
        }
      }
    };
    fetchProfileData();
  }, [user]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
    // Clear error when user types
    if (errors[name]) {
      setErrors({ ...errors, [name]: "" });
    }
  };

  const saveAddressToProfile = async () => {
    if (!user) return;

    // Combine address fields into one string
    const fullAddress = [
      formData.adress,
      formData.postnummer && formData.stad
        ? `${formData.postnummer} ${formData.stad}`
        : formData.postnummer || formData.stad,
    ]
      .filter(Boolean)
      .join(", ");

    if (fullAddress) {
      await supabase
        .from("profiles")
        .update({
          address: fullAddress,
          phone: formData.telefon || null,
        })
        .eq("user_id", user.id);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    const result = formSchema.safeParse(formData);
    if (!result.success) {
      const fieldErrors: Record<string, string> = {};
      result.error.errors.forEach((err) => {
        if (err.path[0]) {
          fieldErrors[err.path[0] as string] = err.message;
        }
      });
      setErrors(fieldErrors);
      return;
    }

    // Save address to profile if user is logged in
    await saveAddressToProfile();

    // For now, just show success - backend integration can be added later
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="text-center py-12 px-6">
        <div className="w-24 h-px bg-primary/40 mx-auto mb-6"></div>
        <h2 className="font-display text-3xl md:text-4xl font-semibold mb-4">
          Tack för din beställning!
        </h2>
        <p className="text-muted-foreground mb-6">
          Vi har tagit emot din beställning för{" "}
          <strong className="text-primary">{formData.abonnemang}</strong> och
          kontaktar dig inom kort.
        </p>
        {onClose && (
          <button onClick={onClose} className="btn-classic">
            Stäng
          </button>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="font-display text-3xl font-semibold mb-2">
          Beställ abonnemang
        </h2>
        <p className="text-muted-foreground">
          Fyll i formuläret så kontaktar vi dig
        </p>
      </div>

      {/* Företagsnamn */}
      <div>
        <label className="block mb-2 font-semibold text-foreground">
          Företagsnamn <span className="text-primary">*</span>
        </label>
        <input
          type="text"
          name="företag"
          value={formData.företag}
          onChange={handleChange}
          className="w-full px-4 py-3 rounded-sm bg-background border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        {errors.företag && (
          <p className="text-destructive text-sm mt-1">{errors.företag}</p>
        )}
      </div>

      {/* E-post & Telefon */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block mb-2 font-semibold text-foreground">
            E-post <span className="text-primary">*</span>
          </label>
          <input
            type="email"
            name="epost"
            value={formData.epost}
            onChange={handleChange}
            className="w-full px-4 py-3 rounded-sm bg-background border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          {errors.epost && (
            <p className="text-destructive text-sm mt-1">{errors.epost}</p>
          )}
        </div>
        <div>
          <label className="block mb-2 font-semibold text-foreground">
            Telefon
          </label>
          <input
            type="tel"
            name="telefon"
            value={formData.telefon}
            onChange={handleChange}
            className="w-full px-4 py-3 rounded-sm bg-background border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
      </div>

      {/* Adress */}
      <div>
        <label className="block mb-2 font-semibold text-foreground">
          Leveransadress
        </label>
        <input
          type="text"
          name="adress"
          value={formData.adress}
          onChange={handleChange}
          className="w-full px-4 py-3 rounded-sm bg-background border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      {/* Postnummer & Stad */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block mb-2 font-semibold text-foreground">
            Postnummer <span className="text-primary">*</span>
          </label>
          <input
            type="text"
            name="postnummer"
            placeholder="t.ex. 114 32"
            value={formData.postnummer}
            onChange={handleChange}
            className={`w-full px-4 py-3 rounded-sm bg-background border text-foreground focus:outline-none focus:ring-2 ${
              getPostalCodeError(formData.postnummer) 
                ? "border-destructive focus:ring-destructive/30" 
                : "border-border focus:ring-primary/30"
            }`}
          />
          {(errors.postnummer || getPostalCodeError(formData.postnummer)) && (
            <p className="text-destructive text-sm mt-1">
              {errors.postnummer || getPostalCodeError(formData.postnummer)}
            </p>
          )}
        </div>
        <div>
          <label className="block mb-2 font-semibold text-foreground">
            Stad
          </label>
          <input
            type="text"
            name="stad"
            value={formData.stad}
            onChange={handleChange}
            className="w-full px-4 py-3 rounded-sm bg-background border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
      </div>

      {/* Abonnemang */}
      <div>
        <label className="block mb-2 font-semibold text-foreground">
          Abonnemang <span className="text-primary">*</span>
        </label>
        <select
          name="abonnemang"
          value={formData.abonnemang}
          onChange={handleChange}
          className="w-full px-4 py-3 rounded-sm bg-background border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">Välj abonnemang</option>
          <option value="Liten (3 kg/vecka)">Liten – 3 kg/vecka – 900 kr</option>
          <option value="Mellan (5 kg/vecka)">Mellan – 5 kg/vecka – 1 500 kr</option>
          <option value="Stor (10 kg/vecka)">Stor – 10 kg/vecka – 4 000 kr</option>
        </select>
        {errors.abonnemang && (
          <p className="text-destructive text-sm mt-1">{errors.abonnemang}</p>
        )}
      </div>

      {/* Kommentarer */}
      <div>
        <label className="block mb-2 font-semibold text-foreground">
          Kommentarer
        </label>
        <textarea
          name="kommentarer"
          value={formData.kommentarer}
          onChange={handleChange}
          className="w-full px-4 py-3 rounded-sm bg-background border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
          rows={3}
        />
      </div>

      {/* Submit */}
      <button type="submit" className="w-full btn-classic py-4 text-lg">
        Skicka beställning
      </button>
    </form>
  );
};

export default AbonnemangForm;
