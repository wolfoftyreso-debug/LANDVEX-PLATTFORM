const Footer = () => {
  return (
    <footer className="py-16 px-6 bg-card border-t border-border">
      <div className="max-w-5xl mx-auto">
        {/* Main footer content */}
        <div className="text-center mb-12">
          <p className="font-display text-3xl font-semibold mb-2 italic text-foreground">
            Lennart Svenssons
          </p>
          <p className="font-display text-xl text-primary mb-4">
            Konditorivaror
          </p>
          <p className="text-muted-foreground italic">
            "Äkta svenskt hantverk sedan 1974"
          </p>
        </div>

        {/* Divider */}
        <div className="divider-ornament mb-8">
          <span className="ornament text-lg">✦</span>
        </div>

        {/* Links */}
        <div className="flex flex-wrap justify-center gap-8 text-sm text-muted-foreground mb-12">
          <a href="#" className="hover:text-primary transition-colors">
            Om konditoriet
          </a>
          <a href="#" className="hover:text-primary transition-colors">
            Vårt sortiment
          </a>
          <a href="#" className="hover:text-primary transition-colors">
            Kontakta oss
          </a>
          <a href="#" className="hover:text-primary transition-colors">
            Allmänna villkor
          </a>
        </div>

        {/* Copyright */}
        <div className="text-center text-muted-foreground text-sm">
          <p>© {new Date().getFullYear()} Lennart Svenssons Konditorivaror</p>
          <p className="mt-1 italic">Alla rättigheter förbehållna</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
