import logoImage from "@/assets/logo.png";
const Header = () => {
  return <header className="fixed top-0 left-0 right-0 z-50 bg-background/95 backdrop-blur-sm border-b border-border">
      <div className="px-6 py-3 flex items-center justify-between">
        <a href="#" className="flex items-center">
          <img alt="Lennart Svensson Konditorivaror" className="h-16 w-auto" src="/lovable-uploads/bc36fcd7-0c6f-48d2-9921-4323413739c7.png" />
        </a>
        
      </div>
    </header>;
};
export default Header;