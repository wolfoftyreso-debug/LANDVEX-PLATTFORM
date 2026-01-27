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
    <section className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="font-display text-center text-4xl md:text-5xl font-bold mb-4">
          Hantverk. Kvalitet. Leveranssäkerhet.
        </h2>
        <p className="text-center text-muted-foreground mb-16 max-w-2xl mx-auto">
          Varje produkt bakas med kärlek och levereras med precision
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {images.map((image, index) => (
            <div
              key={index}
              className="group relative h-64 md:h-72 rounded-2xl overflow-hidden card-glow bg-card"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <img
                src={image.src}
                alt={image.alt}
                className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <p className="absolute bottom-4 left-4 font-medium text-foreground opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                {image.alt}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default GallerySection;
