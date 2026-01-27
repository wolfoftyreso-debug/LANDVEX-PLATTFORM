const Logo = ({ className = "", size = "default" }: { className?: string; size?: "small" | "default" | "large" }) => {
  const sizeClasses = {
    small: "w-16 h-12",
    default: "w-24 h-18",
    large: "w-48 h-36"
  };

  return (
    <div className={`inline-flex items-center justify-center ${sizeClasses[size]} ${className}`}>
      <svg viewBox="0 0 200 150" className="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Outer oval border */}
        <ellipse cx="100" cy="75" rx="95" ry="70" stroke="currentColor" strokeWidth="2" className="text-primary" fill="none" />
        {/* Inner oval border */}
        <ellipse cx="100" cy="75" rx="85" ry="62" stroke="currentColor" strokeWidth="1" className="text-primary" fill="none" />
        
        {/* Text */}
        <text x="100" y="35" textAnchor="middle" className="fill-primary" style={{ fontSize: '10px', fontFamily: 'serif', letterSpacing: '0.2em' }}>
          AKTIEBOLAGET
        </text>
        <text x="100" y="60" textAnchor="middle" className="fill-primary" style={{ fontSize: '22px', fontFamily: 'serif', fontWeight: '600', letterSpacing: '0.1em' }}>
          LENNART
        </text>
        <text x="100" y="85" textAnchor="middle" className="fill-primary" style={{ fontSize: '22px', fontFamily: 'serif', fontWeight: '600', letterSpacing: '0.1em' }}>
          SVENSSON
        </text>
        <text x="100" y="110" textAnchor="middle" className="fill-primary" style={{ fontSize: '10px', fontFamily: 'serif', letterSpacing: '0.25em' }}>
          KONDITORIVAROR
        </text>
      </svg>
    </div>
  );
};

export default Logo;
