import Header from "@/components/Header";
import HeroSection from "@/components/HeroSection";
import HeritageSection from "@/components/HeritageSection";
import PlansSection from "@/components/PlansSection";
import DeliverySection from "@/components/DeliverySection";
import Footer from "@/components/Footer";

const Index = () => {
  return (
    <div className="bg-background text-foreground min-h-screen">
      <Header />
      <HeroSection />
      <HeritageSection />
      <PlansSection />
      <DeliverySection />
      <Footer />
    </div>
  );
};

export default Index;
