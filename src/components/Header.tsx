import logoImage from "@/assets/logo.png";

const Header = () => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur-sm border-b border-border">
      <div className="px-6 py-3 flex items-center justify-between">
        <a href="#" className="flex items-center">
          <img 
            src={logoImage} 
            alt="Lennart Svensson Konditorivaror" 
            className="h-10 w-auto"
          />
        </a>
        
        <nav className="hidden md:flex items-center gap-4 text-sm">
          <a href="#plans" className="bg-primary text-primary-foreground px-4 py-2 rounded-sm hover:bg-primary/90 transition-colors">
            Abonnemang
          </a>
          <a href="#gallery" className="border-2 border-primary text-primary px-4 py-2 rounded-sm hover:bg-primary hover:text-primary-foreground transition-colors">
            Sortiment
          </a>
        </nav>
      </div>
    </header>
  );
};

export default Header;
