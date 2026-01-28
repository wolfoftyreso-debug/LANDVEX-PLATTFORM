import logoImage from "@/assets/logo.png";

const Footer = () => {
  return (
    <footer className="py-16 px-6 bg-card border-t border-border">
      <div className="max-w-5xl mx-auto">
        {/* Main footer content */}
        <div className="text-center mb-12">
          <img 
            src={logoImage} 
            alt="Lennart Svensson Konditorivaror" 
            className="h-24 md:h-32 w-auto mx-auto"
          />
        </div>


        {/* Links */}
        <div className="flex flex-wrap justify-center gap-8 text-sm text-muted-foreground mb-12">
          <a href="#gallery" className="hover:text-primary transition-colors">
            Vårt sortiment
          </a>
          <a href="/contact" className="hover:text-primary transition-colors">
            Kontakta oss
          </a>
        </div>

        {/* Copyright */}
        <div className="text-center text-muted-foreground text-sm">
          <p>© {new Date().getFullYear()} Lennart Svensson Konditorivaror</p>
          <p className="mt-1 italic">Alla rättigheter förbehållna</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
