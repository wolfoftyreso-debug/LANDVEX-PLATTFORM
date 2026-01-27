import bakery1 from "@/assets/bakery-1.jpg";
import bakery2 from "@/assets/bakery-2.jpg";
import bakery3 from "@/assets/bakery-3.jpg";
import bakery4 from "@/assets/bakery-4.jpg";
import bakery5 from "@/assets/bakery-5.jpg";
import bakery6 from "@/assets/bakery-6.jpg";

const images = [
  { src: bakery1, alt: "Kanelbullar" },
  { src: bakery2, alt: "Prinsesstårta" },
  { src: bakery3, alt: "Sorterade kakor" },
  { src: bakery4, alt: "Hantverksbageri" },
  { src: bakery5, alt: "Kardemummabullar" },
  { src: bakery6, alt: "Företagsleverans" },
];

const GallerySection = () => {
  return (
    <section className="py-24 px-6 bg-card">
      <div className="max-w-5xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16">
          <div className="w-24 h-px bg-primary/40 mx-auto mb-6"></div>
          <h2 className="font-display text-4xl md:text-5xl font-semibold mb-4 italic">
            Hantverk & Kvalitet
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Varje produkt bakas med samma recept och omsorg som i vår lilla verkstad sedan 1974
          </p>
        </div>

        {/* Image grid with classic frames */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {images.map((image, index) => (
            <div
              key={index}
              className="group"
            >
              {/* Classic frame effect */}
              <div className="relative p-3 bg-background border border-border card-classic">
                <div className="overflow-hidden">
                  <img
                    src={image.src}
                    alt={image.alt}
                    className="w-full h-56 object-cover transition-transform duration-500 group-hover:scale-105 sepia-[.15]"
                  />
                </div>
                <p className="text-center mt-3 font-display text-lg text-muted-foreground italic">
                  {image.alt}
                </p>
              </div>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
};

export default GallerySection;
