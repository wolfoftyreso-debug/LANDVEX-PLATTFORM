import logoImage from "@/assets/logo.png";

const Logo = ({ className = "", size = "default" }: { className?: string; size?: "small" | "default" | "large" }) => {
  const sizeClasses = {
    small: "h-16",
    default: "h-24",
    large: "h-40"
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
