import logoImage from "@/assets/logo.png";

const HeroSection = () => {
  return (
    <section className="hero-gradient min-h-screen flex flex-col justify-center items-center text-center px-6 py-20 pt-32 relative">
      {/* Decorative top border */}
      <div className="absolute top-0 left-0 right-0 h-2 bg-primary/20" />
      
      <div className="animate-fade-up max-w-4xl">
        <img 
          src={logoImage} 
          alt="Lennart Svensson Konditorivaror" 
          className="h-56 md:h-72 lg:h-80 w-auto mx-auto mb-4 mt-40"
        />

        <p className="text-muted-foreground text-lg mb-8">
          Svenskt konditorhantverk sedan 1953
        </p>

        <div className="divider-ornament my-8">
          <span className="ornament">❧</span>
        </div>

        <p className="max-w-xl mx-auto text-foreground text-xl mb-8 leading-relaxed">
          Äkta fika levererat till ditt företag — varje vecka
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <a
            href="#plans"
            className="btn-classic inline-block px-10 py-4 text-lg rounded-sm"
          >
            Starta Prenumeration
          </a>
          <a
            href="#gallery"
            className="inline-block px-10 py-4 text-lg rounded-sm border-2 border-primary text-primary hover:bg-primary hover:text-primary-foreground transition-colors"
          >
            Se Produkter
          </a>
        </div>
      </div>

      {/* Bottom ornament */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-primary/40 font-display text-2xl">
        ❦
      </div>
    </section>
  );
};

export default HeroSection;
