const HeroSection = () => {
  return (
    <section className="hero-gradient min-h-screen flex flex-col justify-center items-center text-center px-6 relative overflow-hidden">
      {/* Background glow effect */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/10 rounded-full blur-3xl pointer-events-none" />
      
      <div className="relative z-10 animate-fade-up">
        <p className="text-primary uppercase tracking-[0.3em] text-sm font-medium mb-6">
          Lennart Svenssons Konditorivaror
        </p>

        <h1 className="font-display text-5xl md:text-7xl font-bold mb-6 leading-tight">
          Kakabonnemang <br />
          <span className="text-gradient">för företag</span>
        </h1>

        <p className="max-w-xl text-muted-foreground text-lg md:text-xl mb-12 font-light leading-relaxed">
          Premium konditorikakor levererade automatiskt till ert kontor.
          <br />
          Enkel beställning. Fasta leveranser. Maximal arbetsglädje.
        </p>

        <a
          href="#plans"
          className="btn-primary inline-block px-12 py-5 text-lg"
        >
          Starta ert abonnemang
        </a>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-10 left-1/2 -translate-x-1/2 animate-float">
        <div className="w-6 h-10 border-2 border-muted-foreground/30 rounded-full flex justify-center pt-2">
          <div className="w-1 h-2 bg-primary rounded-full" />
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
