import Header from "@/components/Header";
import HeroSection from "@/components/HeroSection";
import GallerySection from "@/components/GallerySection";
import HeritageSection from "@/components/HeritageSection";
import PlansSection from "@/components/PlansSection";
import Footer from "@/components/Footer";

const Index = () => {
  return (
    <div className="bg-background text-foreground min-h-screen">
      <Header />
      <HeroSection />
      <GallerySection />
      <HeritageSection />
      <PlansSection />
      <Footer />
    </div>
  );
};

export default Index;
