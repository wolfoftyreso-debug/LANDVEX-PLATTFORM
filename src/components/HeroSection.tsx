const HeroSection = () => {
  return (
    <section className="hero-gradient min-h-screen flex flex-col justify-center items-center text-center px-6 py-20 relative">
      {/* Decorative top border */}
      <div className="absolute top-0 left-0 right-0 h-2 bg-primary/20" />
      
      <div className="animate-fade-up max-w-4xl">
        {/* Ornamental divider */}
        <div className="divider-ornament mb-8">
          <span className="ornament">✦</span>
        </div>

        <p className="text-primary uppercase tracking-[0.4em] text-sm font-semibold mb-4">
          Sedan 1974
        </p>

        <h1 className="font-display text-5xl md:text-7xl font-semibold mb-4 leading-tight text-foreground italic">
          Lennart Svenssons
        </h1>
        
        <p className="font-display text-3xl md:text-4xl mb-2 text-primary font-medium">
          Konditorivaror
        </p>

        <div className="divider-ornament my-8">
          <span className="ornament">❧</span>
        </div>

        <h2 className="font-display text-2xl md:text-3xl font-medium mb-6 text-foreground">
          Kakabonnemang för företag
        </h2>

        <p className="max-w-xl mx-auto text-muted-foreground text-lg mb-12 leading-relaxed">
          Genuina konditorikakor bakade med tradition och omsorg, 
          levererade direkt till ert kontor. 
          <br />
          <em>Smaken av äkta svenskt hantverk.</em>
        </p>

        <a
          href="#plans"
          className="btn-classic inline-block px-10 py-4 text-lg rounded-sm"
        >
          Starta ert abonnemang
        </a>
      </div>

      {/* Bottom ornament */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-primary/40 font-display text-2xl">
        ❦
      </div>
    </section>
  );
};

export default HeroSection;
