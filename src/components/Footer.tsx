import logoImage from "@/assets/logo.png";
import { Instagram } from "lucide-react";

const TikTokIcon = ({ className }: { className?: string }) => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    viewBox="0 0 24 24" 
    fill="currentColor" 
    className={className}
    width="24" 
    height="24"
  >
    <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5 20.1a6.34 6.34 0 0 0 10.86-4.43v-7a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1-.1z"/>
  </svg>
);

const Footer = () => {
  return (
    <footer className="py-8 px-6 bg-card border-t border-border">
      <div className="max-w-5xl mx-auto">
        {/* Main footer content */}
        <div className="text-center mb-6">
          <img alt="Lennart Svensson Konditorivaror" className="h-24 md:h-32 w-auto mx-auto" src="/lovable-uploads/4f472058-fa74-4c33-9c68-5e8f75f90b24.png" />
        </div>

        {/* Social Media */}
        <div className="flex justify-center items-center gap-6 mb-6">
          <a 
            href="https://instagram.com/konditorivaror" 
            target="_blank" 
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors"
          >
            <Instagram size={18} />
            <span className="text-sm">@konditorivaror</span>
          </a>
          <a 
            href="https://tiktok.com/@konditorivaror" 
            target="_blank" 
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors"
          >
            <TikTokIcon className="w-[18px] h-[18px]" />
            <span className="text-sm">@konditorivaror</span>
          </a>
        </div>

        {/* Links */}
        <div className="flex flex-wrap justify-center gap-6 text-sm text-muted-foreground mb-6">
          <a href="#gallery" className="hover:text-primary transition-colors">
            Vårt sortiment
          </a>
          <a href="/contact" className="hover:text-primary transition-colors">
            Kontakta oss
          </a>
          <a href="/faq" className="hover:text-primary transition-colors">
            FAQ
          </a>
        </div>

        {/* Copyright */}
        <div className="text-center text-muted-foreground text-xs">
          <p>© {new Date().getFullYear()} Lennart Svensson Konditorivaror</p>
          <p className="mt-0.5 italic">Alla rättigheter förbehållna</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;