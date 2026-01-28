import { Truck, Clock, MapPin } from "lucide-react";

const DeliverySection = () => {
  return (
    <section className="py-12 md:py-20 px-4 md:px-6 bg-card">
      <div className="max-w-4xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-10 md:mb-14">
          <div className="w-16 md:w-24 h-px bg-primary/40 mx-auto mb-4 md:mb-6"></div>
          <h2 className="font-display text-2xl md:text-4xl font-semibold mb-3">
            Leverans
          </h2>
          <p className="text-muted-foreground text-sm md:text-lg">
            Färska kakor direkt till ert kontor – varje vecka
          </p>
        </div>

        {/* Info cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
          {/* Leveransområde */}
          <div className="text-center p-6">
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-primary/10 flex items-center justify-center">
              <MapPin className="w-6 h-6 text-primary" />
            </div>
            <h3 className="font-display text-lg md:text-xl font-semibold mb-2">
              Storstockholm
            </h3>
            <p className="text-muted-foreground text-sm">
              Vi levererar till alla företag inom Storstockholmsområdet.
            </p>
          </div>

          {/* Leveransdag */}
          <div className="text-center p-6">
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-primary/10 flex items-center justify-center">
              <Clock className="w-6 h-6 text-primary" />
            </div>
            <h3 className="font-display text-lg md:text-xl font-semibold mb-2">
              Veckoleverans
            </h3>
            <p className="text-muted-foreground text-sm">
              Samma dag varje vecka – ni väljer vilken dag som passar er bäst.
            </p>
          </div>

          {/* Leveranstid */}
          <div className="text-center p-6">
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-primary/10 flex items-center justify-center">
              <Truck className="w-6 h-6 text-primary" />
            </div>
            <h3 className="font-display text-lg md:text-xl font-semibold mb-2">
              Dagtid
            </h3>
            <p className="text-muted-foreground text-sm">
              Leverans under kontorstid. Meddela oss om ni har särskilda önskemål.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default DeliverySection;