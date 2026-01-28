import logoImage from "@/assets/logo.png";
import heroBakeryImage from "@/assets/hero-bakery-wide.jpg";
const HeroSection = () => {
  return <section className="relative left-1/2 w-screen -translate-x-1/2 overflow-x-clip flex flex-col justify-center items-center text-center min-h-[70vh] pb-0 mb-0">
      {/* Background image */}
      <div className="pointer-events-none absolute inset-0 bg-cover bg-center" style={{
        backgroundImage: `url(${heroBakeryImage})`,
        opacity: 0.4,
        maskImage: 'linear-gradient(to bottom, black 50%, transparent 100%)',
        WebkitMaskImage: 'linear-gradient(to bottom, black 50%, transparent 100%)'
      }} />
      
      <div className="animate-fade-up max-w-4xl relative z-10 px-6 py-16">
        <img alt="Lennart Svensson Konditorivaror" className="h-56 md:h-72 lg:h-80 w-auto mx-auto mb-1 mt-8" src="/lovable-uploads/8658a13b-f1d4-45db-b92b-3e22abb6ee1b.png" />

        <p className="text-muted-foreground text-lg mb-4">
          Svenskt konditorhantverk sedan 1953
        </p>

        <div className="w-40 h-px bg-primary/40 mx-auto my-4"></div>

        <p className="max-w-xl mx-auto text-foreground text-xl mb-8 leading-relaxed">
          Äkta fika levererat till ditt företag — varje vecka
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <a href="#abonnemang" className="btn-classic inline-block px-10 py-4 text-lg rounded-sm">
            Starta Prenumeration
          </a>
          <a href="#gallery" className="inline-block px-10 py-4 text-lg rounded-sm border-2 border-primary text-primary hover:bg-primary hover:text-primary-foreground transition-colors">
            Sortiment
          </a>
        </div>
      </div>

    </section>;
};
export default HeroSection;