import logoImage from "@/assets/logo.png";

const Logo = ({ className = "", size = "default" }: { className?: string; size?: "small" | "default" | "large" }) => {
  const sizeClasses = {
    small: "h-12",
    default: "h-20",
    large: "h-32"
  };

  return (
    <img 
      src={logoImage} 
      alt="Lennart Svensson Konditorivaror" 
      className={`${sizeClasses[size]} w-auto ${className}`}
    />
  );
};

export default Logo;
