import { Truck, Clock, MapPin } from "lucide-react";

const DeliverySection = () => {
  return (
    <section className="py-8 md:py-12 px-4 md:px-6 bg-card">
      <div className="max-w-4xl mx-auto">
        {/* Info cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
          {/* Leveransområde */}
          <div className="text-center p-4">
            <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-primary/10 flex items-center justify-center">
              <MapPin className="w-5 h-5 text-primary" />
            </div>
            <h3 className="font-display text-base md:text-lg font-semibold mb-1">
              Storstockholm
            </h3>
            <p className="text-muted-foreground text-sm">
              Vi levererar till alla företag inom Storstockholmsområdet.
            </p>
          </div>

          {/* Leveransdag */}
          <div className="text-center p-4">
            <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-primary/10 flex items-center justify-center">
              <Clock className="w-5 h-5 text-primary" />
            </div>
            <h3 className="font-display text-base md:text-lg font-semibold mb-1">
              Veckoleverans
            </h3>
            <p className="text-muted-foreground text-sm">
              Kakorna levereras samma dag varje vecka
            </p>
          </div>

          {/* Leveranstid */}
          <div className="text-center p-4">
            <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-primary/10 flex items-center justify-center">
              <Truck className="w-5 h-5 text-primary" />
            </div>
            <h3 className="font-display text-base md:text-lg font-semibold mb-1">
              Dagtid
            </h3>
            <p className="text-muted-foreground text-sm">
              Kakorna levereras alltid under dagtid
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default DeliverySection;