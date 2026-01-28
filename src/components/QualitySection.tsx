const QualitySection = () => {
  const promises = [
    {
      title: "Dagsfärska kakor",
      description: "Alla kakor bakas samma dag som de levereras – aldrig frysta, alltid färska.",
    },
    {
      title: "Svensk hantverkstradition",
      description: "Recept som gått i arv sedan 1974, med samma omsorg och kvalitet i varje kaka.",
    },
    {
      title: "Utvalda råvaror",
      description: "Vi använder endast de finaste ingredienserna – riktigt smör, äkta vanilj och mandel av högsta kvalitet.",
    },
  ];

  return (
    <section className="py-12 md:py-20 px-4 md:px-6 bg-background">
      <div className="max-w-4xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-10 md:mb-14">
          <div className="w-16 md:w-24 h-px bg-primary/40 mx-auto mb-4 md:mb-6"></div>
          <h2 className="font-display text-2xl md:text-4xl font-semibold mb-3">
            Vårt löfte
          </h2>
          <p className="font-display text-base md:text-xl italic text-muted-foreground">
            Kvalitet i varje kaka, varje leverans
          </p>
        </div>

        {/* Promises */}
        <div className="space-y-6 md:space-y-8">
          {promises.map((promise, index) => (
            <div 
              key={index} 
              className="flex gap-4 md:gap-6 items-start"
            >
              <div className="flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="font-display text-primary font-semibold text-sm md:text-base">
                  {index + 1}
                </span>
              </div>
              <div>
                <h3 className="font-display text-lg md:text-xl font-semibold mb-1">
                  {promise.title}
                </h3>
                <p className="text-muted-foreground text-sm md:text-base">
                  {promise.description}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom tagline */}
        <div className="text-center mt-10 md:mt-14">
          <p className="font-display text-sm md:text-base italic text-muted-foreground">
            — Lennart Svenssons Konditorivaror, sedan 1974 —
          </p>
        </div>
      </div>
    </section>
  );
};

export default QualitySection;