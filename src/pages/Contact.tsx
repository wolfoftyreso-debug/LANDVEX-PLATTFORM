import { useState } from "react";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";
import { Send, ArrowLeft } from "lucide-react";

const contactSchema = z.object({
  email: z.string().trim().email("Ogiltig e-postadress").max(255, "Max 255 tecken"),
  company: z.string().trim().min(1, "Företag krävs").max(100, "Max 100 tecken"),
  message: z.string().trim().min(1, "Meddelande krävs").max(2000, "Max 2000 tecken"),
});

type ContactForm = z.infer<typeof contactSchema>;

const Contact = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<ContactForm>({
    email: "",
    company: "",
    message: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const validation = contactSchema.safeParse(form);
    if (!validation.success) {
      toast.error(validation.error.errors[0].message);
      return;
    }

    setIsSubmitting(true);

    try {
      const { error } = await supabase.functions.invoke("send-contact-email", {
        body: {
          email: form.email,
          company: form.company,
          message: form.message,
        },
      });

      if (error) {
        throw error;
      }

      setIsSubmitted(true);
      toast.success("Tack för ditt meddelande!");
    } catch (error: any) {
      console.error("Contact form error:", error);
      toast.error("Något gick fel. Försök igen senare.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <div className="px-6 pt-32">
        <button
          onClick={() => navigate("/")}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors"
        >
          <ArrowLeft size={16} />
          <span>Tillbaka till startsidan</span>
        </button>
      </div>
      <main className="flex-1 pt-8 pb-16 px-4">
        <div className="max-w-xl mx-auto">

          {/* Header */}
          <div className="text-center mb-10">
            <div className="w-16 h-px bg-primary/40 mx-auto mb-6"></div>
            <h1 className="font-display text-3xl md:text-4xl font-semibold mb-3">
              Kontakta oss
            </h1>
            <p className="text-muted-foreground">
              Har du frågor om våra abonnemang eller vill veta mer? Hör av dig!
            </p>
          </div>

          {isSubmitted ? (
            <div className="bg-card border border-border rounded-lg p-8 text-center">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <Send className="w-8 h-8 text-primary" />
              </div>
              <h2 className="font-display text-2xl font-semibold mb-2">
                Tack för ditt meddelande!
              </h2>
              <p className="text-muted-foreground mb-6">
                Vi återkommer till dig så snart som möjligt.
              </p>
              <Button onClick={() => navigate("/")} variant="outline">
                Tillbaka till startsidan
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="bg-card border border-border rounded-lg p-6 md:p-8 space-y-5">
              <div className="space-y-2">
                <Label htmlFor="company">Företag *</Label>
                <Input
                  id="company"
                  type="text"
                  value={form.company}
                  onChange={(e) => setForm({ ...form, company: e.target.value })}
                  placeholder="Företagsnamn"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">E-post *</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="din@epost.se"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="message">Meddelande *</Label>
                <Textarea
                  id="message"
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  placeholder="Skriv ditt meddelande här..."
                  rows={5}
                  required
                />
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  "Skickar..."
                ) : (
                  <>
                    <Send className="w-4 h-4 mr-2" />
                    Skicka meddelande
                  </>
                )}
              </Button>
            </form>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Contact;
