import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  RatingStars,
  TrustScoreBadge,
  VerificationBadge,
} from "@/components/marketplace/badges";
import EmptyState from "@/components/marketplace/EmptyState";
import {
  getCompanyBySlug,
  listCompanyServices,
  listPortfolio,
} from "@/modules/companies/api";
import { listCompanyReviews } from "@/modules/reviews/api";
import { countryName, languageName } from "@/modules/core/countries";
import {
  MapPin,
  Globe,
  Mail,
  Phone,
  Users,
  CalendarDays,
  Briefcase,
  Repeat,
  FileText,
  ImageIcon,
  Star,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { format } from "date-fns";

function Fact({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof MapPin;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <div>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="font-medium">{value}</div>
      </div>
    </div>
  );
}

export default function CompanyProfile() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();

  const { data: company, isLoading } = useQuery({
    queryKey: ["company", slug],
    queryFn: () => getCompanyBySlug(slug!),
    enabled: !!slug,
  });

  const { data: services } = useQuery({
    queryKey: ["company-services", company?.id],
    queryFn: () => listCompanyServices(company!.id),
    enabled: !!company,
  });

  const { data: portfolio } = useQuery({
    queryKey: ["company-portfolio", company?.id],
    queryFn: () => listPortfolio(company!.id),
    enabled: !!company,
  });

  const { data: reviews } = useQuery({
    queryKey: ["company-reviews", company?.id],
    queryFn: () => listCompanyReviews(company!.id),
    enabled: !!company,
  });

  // SEO: permanent URL per company + descriptive title
  useEffect(() => {
    if (company) {
      document.title = `${company.name} — verified on Baltic Bridge`;
    }
    return () => {
      document.title = "Baltic Bridge";
    };
  }, [company]);

  if (isLoading) {
    return (
      <SiteLayout>
        <div className="container mx-auto px-4 py-16 text-muted-foreground">
          Loading company profile…
        </div>
      </SiteLayout>
    );
  }

  if (!company) {
    return (
      <SiteLayout>
        <div className="container mx-auto px-4 py-16">
          <EmptyState
            icon={Briefcase}
            title="Company not found"
            description="The company you are looking for does not exist or has been removed."
            action={<Button onClick={() => navigate("/companies")}>Browse companies</Button>}
          />
        </div>
      </SiteLayout>
    );
  }

  return (
    <SiteLayout>
      {/* Cover */}
      <div
        className="h-44 w-full bg-gradient-to-r from-primary to-primary/70 bg-cover bg-center md:h-56"
        style={company.cover_url ? { backgroundImage: `url(${company.cover_url})` } : undefined}
      />

      <div className="container mx-auto px-4">
        {/* Header card */}
        <div className="card-elevated -mt-14 flex flex-col gap-4 p-6 md:flex-row md:items-end md:justify-between">
          <div className="flex items-end gap-4">
            <Avatar className="h-24 w-24 rounded-xl border-4 border-card shadow">
              <AvatarImage src={company.logo_url ?? undefined} alt={company.name} />
              <AvatarFallback className="rounded-xl bg-primary/10 text-2xl font-bold text-primary">
                {company.name.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-bold">{company.name}</h1>
                <VerificationBadge level={company.verification_level} />
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <MapPin className="h-4 w-4" />
                  {[company.city, countryName(company.country)].filter(Boolean).join(", ")}
                </span>
                <RatingStars rating={Number(company.rating_avg)} count={company.rating_count} />
                <Badge
                  variant="outline"
                  className={
                    company.availability === "available"
                      ? "border-emerald-500 text-emerald-600"
                      : ""
                  }
                >
                  {company.availability === "available"
                    ? "Available for work"
                    : company.availability === "busy"
                      ? "Limited availability"
                      : "Currently unavailable"}
                </Badge>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-xs text-muted-foreground">Trust Score</div>
              <TrustScoreBadge score={Number(company.trust_score)} className="text-sm" />
            </div>
            <Button onClick={() => navigate(`/rfq/new`)}>
              <FileText className="mr-1.5 h-4 w-4" />
              Request a quote
            </Button>
          </div>
        </div>

        {/* Trust facts strip */}
        <div className="mt-4 grid grid-cols-2 gap-4 rounded-lg border bg-card p-4 text-center sm:grid-cols-4">
          <div>
            <div className="text-xl font-bold">{company.completed_projects}</div>
            <div className="text-xs text-muted-foreground">Completed projects</div>
          </div>
          <div>
            <div className="text-xl font-bold">{company.repeat_customers}</div>
            <div className="text-xs text-muted-foreground">Repeat customers</div>
          </div>
          <div>
            <div className="text-xl font-bold">
              {company.response_rate != null ? `${Math.round(Number(company.response_rate))}%` : "—"}
            </div>
            <div className="text-xs text-muted-foreground">Response rate</div>
          </div>
          <div>
            <div className="text-xl font-bold">
              {format(new Date(company.created_at), "yyyy")}
            </div>
            <div className="text-xs text-muted-foreground">On Baltic Bridge since</div>
          </div>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="about" className="mt-6 pb-16">
          <TabsList>
            <TabsTrigger value="about">About</TabsTrigger>
            <TabsTrigger value="services">Services</TabsTrigger>
            <TabsTrigger value="portfolio">Portfolio</TabsTrigger>
            <TabsTrigger value="reviews">
              Reviews {company.rating_count > 0 && `(${company.rating_count})`}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="about" className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="card-elevated p-6 lg:col-span-2">
              <h2 className="font-semibold">About {company.name}</h2>
              <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
                {company.description ?? "This company has not added a description yet."}
              </p>
              {(company.certifications.length > 0 || company.licenses.length > 0) && (
                <div className="mt-6 space-y-3">
                  {company.certifications.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold">Certifications</h3>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {company.certifications.map((c) => (
                          <Badge key={c} variant="secondary" className="gap-1">
                            <CheckCircle2 className="h-3 w-3" /> {c}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {company.licenses.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold">Licenses</h3>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {company.licenses.map((l) => (
                          <Badge key={l} variant="secondary" className="gap-1">
                            <ShieldCheck className="h-3 w-3" /> {l}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="card-elevated space-y-4 p-6">
              <h2 className="font-semibold">Company facts</h2>
              {company.year_founded && (
                <Fact icon={CalendarDays} label="Founded" value={company.year_founded} />
              )}
              {company.employee_count && (
                <Fact icon={Users} label="Employees" value={company.employee_count} />
              )}
              {company.vat_number && (
                <Fact
                  icon={ShieldCheck}
                  label="VAT number"
                  value={
                    <span className="inline-flex items-center gap-1">
                      {company.vat_number}
                      {company.vat_verified && (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      )}
                    </span>
                  }
                />
              )}
              {company.org_number && (
                <Fact icon={Briefcase} label="Organization number" value={company.org_number} />
              )}
              {company.countries_served.length > 0 && (
                <Fact
                  icon={Globe}
                  label="Countries served"
                  value={company.countries_served.map(countryName).join(", ")}
                />
              )}
              {company.languages.length > 0 && (
                <Fact
                  icon={Repeat}
                  label="Languages"
                  value={company.languages.map(languageName).join(", ")}
                />
              )}
              {company.website && (
                <Fact
                  icon={Globe}
                  label="Website"
                  value={
                    <a
                      href={company.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      {company.website.replace(/^https?:\/\//, "")}
                    </a>
                  }
                />
              )}
              {company.contact_email && (
                <Fact icon={Mail} label="Email" value={company.contact_email} />
              )}
              {company.contact_phone && (
                <Fact icon={Phone} label="Phone" value={company.contact_phone} />
              )}
            </div>
          </TabsContent>

          <TabsContent value="services" className="mt-6">
            {services && services.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {services.map((s) => (
                  <Badge key={s.id} variant="outline" className="px-3 py-1.5 text-sm">
                    {s.categories?.name}
                  </Badge>
                ))}
              </div>
            ) : (
              <EmptyState icon={Briefcase} title="No services listed yet" />
            )}
          </TabsContent>

          <TabsContent value="portfolio" className="mt-6">
            {portfolio && portfolio.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {portfolio.map((item) => (
                  <div key={item.id} className="card-elevated overflow-hidden">
                    {item.image_url ? (
                      <img
                        src={item.image_url}
                        alt={item.title}
                        className="h-44 w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-44 items-center justify-center bg-muted">
                        <ImageIcon className="h-8 w-8 text-muted-foreground/50" />
                      </div>
                    )}
                    <div className="p-4">
                      <h3 className="font-semibold">{item.title}</h3>
                      {item.description && (
                        <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                          {item.description}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={ImageIcon}
                title="No portfolio yet"
                description="This company has not published project references yet."
              />
            )}
          </TabsContent>

          <TabsContent value="reviews" className="mt-6">
            {reviews && reviews.length > 0 ? (
              <div className="space-y-4">
                {reviews.map((review) => (
                  <div key={review.id} className="card-elevated p-5">
                    <div className="flex items-center justify-between">
                      <RatingStars rating={review.rating_overall} />
                      <span className="text-xs text-muted-foreground">
                        {format(new Date(review.created_at), "d MMM yyyy")} · Verified customer
                      </span>
                    </div>
                    {review.project_description && (
                      <p className="mt-2 text-sm font-medium">{review.project_description}</p>
                    )}
                    {review.comment && (
                      <p className="mt-1 text-sm text-muted-foreground">{review.comment}</p>
                    )}
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground sm:grid-cols-5">
                      {(
                        [
                          ["Communication", review.rating_communication],
                          ["Quality", review.rating_quality],
                          ["Price", review.rating_price],
                          ["Delivery", review.rating_delivery],
                          ["Professionalism", review.rating_professionalism],
                        ] as const
                      ).map(
                        ([label, value]) =>
                          value != null && (
                            <span key={label}>
                              {label}: <strong>{value}/5</strong>
                            </span>
                          ),
                      )}
                    </div>
                    {review.would_recommend && (
                      <Badge variant="secondary" className="mt-3 gap-1">
                        <CheckCircle2 className="h-3 w-3" /> Would recommend
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Star}
                title="No reviews yet"
                description="Reviews can only be written by verified customers after completed work."
              />
            )}
          </TabsContent>
        </Tabs>
      </div>
    </SiteLayout>
  );
}
