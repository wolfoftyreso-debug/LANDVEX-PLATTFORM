import Header from "@/components/Header";
import Footer from "@/components/Footer";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const faqs = [
  {
    question: "Vilka leveransområden har ni?",
    answer: "Vi levererar till alla typer av företag i Storstockholm – restauranger, caféer, konditorier, hotell, kontor och andra verksamheter som vill bjuda sina gäster och anställda på kvalitetsfika."
  },
  {
    question: "Hur ofta sker leveranserna?",
    answer: "Vi levererar en gång i veckan, samma dag varje vecka, så du alltid har färska bakverk till dina gäster och anställda."
  },
  {
    question: "Kan jag ändra mitt abonnemang?",
    answer: "Ja, du kan när som helst ändra eller pausa ditt abonnemang genom att kontakta oss."
  }
];

const FAQ = () => {
  return (
    <div className="bg-background text-foreground min-h-screen">
      <Header />
      <main className="max-w-3xl mx-auto px-6 pt-32 pb-16">
        <h1 className="text-3xl md:text-4xl font-bold text-center mb-4">
          Vanliga frågor
        </h1>
        <p className="text-muted-foreground text-center mb-10">
          Här hittar du svar på de vanligaste frågorna om våra produkter och tjänster.
        </p>
        
        <Accordion type="single" collapsible className="w-full">
          {faqs.map((faq, index) => (
            <AccordionItem key={index} value={`item-${index}`}>
              <AccordionTrigger className="text-left">
                {faq.question}
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground">
                {faq.answer}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </main>
      <Footer />
    </div>
  );
};

export default FAQ;
