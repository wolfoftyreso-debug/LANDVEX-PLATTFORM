const Footer = () => {
  return (
    <footer className="py-16 px-6 border-t border-border">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="text-center md:text-left">
            <p className="font-display text-xl font-semibold mb-1">
              Lennart Svenssons Konditorivaror
            </p>
            <p className="text-muted-foreground text-sm">
              Premium kakor till svenska kontor sedan 1974
            </p>
          </div>

          <div className="flex gap-8 text-sm text-muted-foreground">
            <a href="#" className="hover:text-primary transition-colors">
              Om oss
            </a>
            <a href="#" className="hover:text-primary transition-colors">
              Kontakt
            </a>
            <a href="#" className="hover:text-primary transition-colors">
              Villkor
            </a>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-border text-center text-muted-foreground text-sm">
          © {new Date().getFullYear()} Lennart Svenssons Konditorivaror — Alla
          rättigheter förbehållna
        </div>
      </div>
    </footer>
  );
};

export default Footer;
