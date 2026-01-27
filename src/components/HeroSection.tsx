import logoImage from "@/assets/logo.png";

const HeroSection = () => {
  return (
    <section className="hero-gradient flex flex-col justify-center items-center text-center px-6 py-16 pt-20 pb-12 relative">
      {/* Decorative top border */}
      <div className="absolute top-0 left-0 right-0 h-2 bg-primary/20" />
      
      <div className="animate-fade-up max-w-4xl">
        <img 
          src={logoImage} 
          alt="Lennart Svensson Konditorivaror" 
          className="h-56 md:h-72 lg:h-80 w-auto mx-auto mb-1 mt-8"
        />

        <p className="text-muted-foreground text-lg mb-8">
          Svenskt konditorhantverk sedan 1953
        </p>


        <div className="w-24 h-px bg-primary/40 mx-auto my-8"></div>

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
            Sortiment
          </a>
        </div>
      </div>

    </section>
  );
};

export default HeroSection;
