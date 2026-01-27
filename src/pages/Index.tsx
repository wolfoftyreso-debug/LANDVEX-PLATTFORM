import HeroSection from "@/components/HeroSection";
import GallerySection from "@/components/GallerySection";
import PlansSection from "@/components/PlansSection";
import Footer from "@/components/Footer";

const Index = () => {
  return (
    <div className="bg-background text-foreground min-h-screen">
      <HeroSection />
      <GallerySection />
      <PlansSection />
      <Footer />
    </div>
  );
};

export default Index;
