const Header = () => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur-sm border-b border-border">
      <div className="px-6 py-4 flex items-center justify-end">
        
        <nav className="hidden md:flex items-center gap-4 text-sm">
          <a href="#plans" className="border-2 border-primary text-primary px-4 py-2 rounded-sm hover:bg-primary hover:text-primary-foreground transition-colors">
            Abonnemang
          </a>
          <a href="#gallery" className="bg-primary text-primary-foreground px-4 py-2 rounded-sm hover:bg-primary/90 transition-colors">
            Sortiment
          </a>
        </nav>
      </div>
    </header>
  );
};

export default Header;
