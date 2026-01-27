import { useEffect, useRef, useState } from "react";
import bakeryHeritageImage from "@/assets/bakery-heritage.jpg";
import mandelkubbImage from "@/assets/mandelkubb.jpg";
import kolasnittImage from "@/assets/kolasnitt.jpg";
import chokladsnittImage from "@/assets/chokladsnitt.jpg";

const cookies = [
  {
    name: "Mandelkubben",
    image: mandelkubbImage,
    description: "Den traditionella mandelkubben – nötig och klassisk med mild sötma och tydlig mandelsmak. En riktig svensk fikakaka.",
  },
  {
    name: "Kolasnitten",
    image: kolasnittImage,
    description: "Den klassiska kolakakan med fyllig, smörig kolasmak som smälter i munnen. Spröd på ytan, seg i mitten.",
  },
  {
    name: "Chokladsnitten",
    image: chokladsnittImage,
    description: "En chokladälskares favorit – perfekt balans mellan sötma och rik chokladsmak. Krispig på kanterna, seg i mitten.",
  },
];

const HeritageSection = () => {
  const [heroVisible, setHeroVisible] = useState(false);
  const [cookiesVisible, setCookiesVisible] = useState(false);
  const heroRef = useRef<HTMLDivElement>(null);
  const cookiesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observerOptions = {
      threshold: 0.1,
      rootMargin: "0px 0px -100px 0px",
    };

    const heroObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setHeroVisible(true);
        }
      });
    }, observerOptions);

    const cookiesObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setCookiesVisible(true);
        }
      });
    }, observerOptions);

    if (heroRef.current) heroObserver.observe(heroRef.current);
    if (cookiesRef.current) cookiesObserver.observe(cookiesRef.current);

    return () => {
      heroObserver.disconnect();
      cookiesObserver.disconnect();
    };
  }, []);

  return (
    <section className="bg-secondary/30 py-24 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Heritage Hero */}
        <div
          ref={heroRef}
          className={`transition-all duration-[1500ms] ease-out ${
            heroVisible
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-16"
          }`}
        >
          {/* Image */}
          <div className="relative rounded-sm overflow-hidden mb-12 shadow-xl">
            <img
              src={bakeryHeritageImage}
              alt="Traditionellt svenskt konditori"
              className="w-full h-[400px] md:h-[500px] object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent" />
          </div>

          {/* Text Content */}
          <div className="text-center max-w-3xl mx-auto">
            <div className="divider-ornament mb-6">
              <span className="ornament">✦</span>
            </div>
            <h2 className="font-display text-3xl md:text-4xl lg:text-5xl font-semibold mb-6">
              Hantverk & Kvalitet
            </h2>
            <div className="space-y-4 text-foreground/80 text-lg leading-relaxed">
              <p>
                Våra recept grundar sig i det klassiska <em className="text-primary">Svenska Konditorilexikon från 1954</em> och 
                har förädlats genom generationer av bagare. Vi använder bara riktigt smör, 
                färska mandlar och äkta choklad.
              </p>
              <p>
                Varje kaka formas för hand med samma omsorg som traditionella 
                konditorer alltid har gjort. Det är så det har varit i över 70 år, och så det alltid kommer att vara.
              </p>
            </div>
          </div>
        </div>

        {/* Cookies Grid */}
        <div
          ref={cookiesRef}
          className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8"
        >
          {cookies.map((cookie, index) => (
            <div
              key={cookie.name}
              className={`transition-all duration-700 ease-out ${
                cookiesVisible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-12"
              }`}
              style={{
                transitionDelay: cookiesVisible ? `${index * 200}ms` : "0ms",
              }}
            >
              <div className="text-center">
                <div className="aspect-square overflow-hidden rounded-sm mb-6">
                  <img
                    src={cookie.image}
                    alt={cookie.name}
                    className="w-full h-full object-cover hover:scale-105 transition-transform duration-500"
                  />
                </div>
                <h3 className="font-display text-2xl font-semibold text-foreground mb-3">
                  {cookie.name}
                </h3>
                <p className="text-foreground/70 leading-relaxed">
                  {cookie.description}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom ornament */}
        <div className="text-center mt-16 text-primary/40 font-display text-2xl">
          ❦
        </div>
      </div>
    </section>
  );
};

export default HeritageSection;
