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
    question: "Hur beställer jag produkter?",
    answer: "Du kan enkelt beställa genom att välja ett av våra abonnemang och fylla i dina uppgifter. Vi kontaktar dig sedan för att bekräfta din beställning."
  },
  {
    question: "Vilka leveransområden har ni?",
    answer: "Vi levererar till företag och konditorier i hela Sverige. Kontakta oss för mer information om leverans till just ditt område."
  },
  {
    question: "Hur ofta sker leveranserna?",
    answer: "Leveransfrekvensen beror på vilket abonnemang du väljer. Vi erbjuder vecko-, varannan vecka- och månadsleveranser."
  },
  {
    question: "Kan jag ändra mitt abonnemang?",
    answer: "Ja, du kan när som helst ändra eller pausa ditt abonnemang genom att kontakta oss."
  },
  {
    question: "Hur hanterar ni allergener?",
    answer: "Alla våra produkter är tydligt märkta med innehållsförteckning. Kontakta oss om du har specifika frågor om allergener."
  },
  {
    question: "Vad är er returpolicy?",
    answer: "Vi strävar efter högsta kvalitet. Om du inte är nöjd med din leverans, kontakta oss inom 24 timmar så löser vi det."
  }
];

const FAQ = () => {
  return (
    <div className="bg-background text-foreground min-h-screen">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-16">
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
