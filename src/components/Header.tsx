import Logo from "./Logo";

const Header = () => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur-sm border-b border-border">
      <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
        <a href="/" className="flex items-center">
          <Logo size="small" />
        </a>
        
        <nav className="hidden md:flex items-center gap-6 text-sm">
          <a href="#gallery" className="text-muted-foreground hover:text-primary transition-colors">
            Sortiment
          </a>
          <a href="#plans" className="bg-primary text-primary-foreground px-4 py-2 rounded-sm hover:bg-primary/90 transition-colors">
            Abonnemang
          </a>
        </nav>
      </div>
    </header>
  );
};

export default Header;
