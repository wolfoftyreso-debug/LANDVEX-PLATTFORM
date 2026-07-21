import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import { Button } from "@/components/ui/button";
import CompanyCard from "@/components/marketplace/CompanyCard";
import { VERTICALS } from "@/modules/marketplace/config";
import { listCompanies } from "@/modules/companies/api";
import {
  ShieldCheck,
  FileText,
  MessagesSquare,
  Star,
  ArrowRight,
  Truck,
  BadgeCheck,
} from "lucide-react";

const STEPS = [
  {
    icon: FileText,
    title: "Describe your project",
    text: "Post a request with photos, budget and deadline — free and without obligation.",
  },
  {
    icon: MessagesSquare,
    title: "Receive quotes",
    text: "Verified companies matching your request respond with their best offers.",
  },
  {
    icon: BadgeCheck,
    title: "Choose with confidence",
    text: "Compare trust scores, verification levels and reviews before you decide.",
  },
  {
    icon: Star,
    title: "Review the work",
    text: "After completion, your verified review builds long-term trust on the platform.",
  },
];

export default function Landing() {
  const navigate = useNavigate();
  const { data: featured } = useQuery({
    queryKey: ["featured-companies"],
    queryFn: () => listCompanies(),
  });

  return (
    <SiteLayout>
      {/* Hero */}
      <section className="border-b bg-gradient-to-b from-primary/5 to-background">
        <div className="container mx-auto px-4 py-20 text-center md:py-28">
          <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-primary" />
            Every company is verified before it can quote
          </span>
          <h1 className="mx-auto mt-6 max-w-3xl text-balance text-4xl font-extrabold md:text-6xl">
            Europe's marketplace for{" "}
            <span className="text-primary">verified</span> professional services
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-balance text-lg text-muted-foreground">
            Get quotes from trusted construction companies, car workshops,
            bakeries and manufacturers across Europe. Compare trust scores,
            reviews and verification levels — then hire with confidence.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" onClick={() => navigate("/rfq/new")}>
              Request quotes — free
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline" onClick={() => navigate("/companies")}>
              Browse companies
            </Button>
          </div>
        </div>
      </section>

      {/* Verticals */}
      <section className="container mx-auto px-4 py-16">
        <h2 className="text-center text-2xl font-bold md:text-3xl">Marketplaces</h2>
        <p className="mt-2 text-center text-muted-foreground">
          Services and production — the platform is built to host many more verticals.
        </p>
        <div className="mx-auto mt-8 grid max-w-4xl gap-6 md:grid-cols-2">
          {VERTICALS.map((v) => (
            <Link
              key={v.slug}
              to={`/companies?vertical=${v.slug}`}
              className="card-elevated group p-8"
            >
              <v.icon className="h-10 w-10 text-primary" />
              <h3 className="mt-4 text-xl font-bold group-hover:text-primary">
                {v.label}
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">{v.tagline}</p>
              <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
                Explore {v.label.toLowerCase()}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y bg-card">
        <div className="container mx-auto px-4 py-16">
          <h2 className="text-center text-2xl font-bold md:text-3xl">How Baltic Bridge works</h2>
          <p className="mx-auto mt-2 max-w-xl text-center text-muted-foreground">
            We never perform the work — we connect you with verified companies
            and keep every step transparent.
          </p>
          <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <div key={step.title} className="text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <step.icon className="h-6 w-6 text-primary" />
                </div>
                <div className="mt-3 text-xs font-semibold text-muted-foreground">
                  STEP {i + 1}
                </div>
                <h3 className="mt-1 font-semibold">{step.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{step.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured companies */}
      {featured && featured.length > 0 && (
        <section className="container mx-auto px-4 py-16">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold">Top-rated companies</h2>
            <Button variant="ghost" onClick={() => navigate("/companies")}>
              View all
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {featured.slice(0, 6).map((company) => (
              <CompanyCard key={company.id} company={company} />
            ))}
          </div>
        </section>
      )}

      {/* For companies CTA */}
      <section className="container mx-auto px-4 pb-20">
        <div className="card-elevated flex flex-col items-center gap-6 bg-primary p-10 text-center text-primary-foreground md:flex-row md:text-left">
          <div className="flex-1">
            <h2 className="text-2xl font-bold">Run a construction company or workshop?</h2>
            <p className="mt-2 opacity-90">
              Create your standardized company profile, get verified, and receive
              qualified requests from customers across Europe. Your trust score
              grows with every completed project.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Truck className="hidden h-10 w-10 opacity-80 md:block" />
            <Button
              size="lg"
              variant="secondary"
              onClick={() => navigate("/company/register")}
            >
              List your company
            </Button>
          </div>
        </div>
      </section>
    </SiteLayout>
  );
}
