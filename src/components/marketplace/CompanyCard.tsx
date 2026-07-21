import { Link } from "react-router-dom";
import { MapPin, Briefcase } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  RatingStars,
  TrustScoreBadge,
  VerificationBadge,
} from "@/components/marketplace/badges";
import { countryName } from "@/modules/core/countries";
import type { Company } from "@/modules/companies/types";

export default function CompanyCard({ company }: { company: Company }) {
  return (
    <Link
      to={`/company/${company.slug}`}
      className="card-elevated block p-5"
    >
      <div className="flex items-start gap-4">
        <Avatar className="h-14 w-14 rounded-lg">
          <AvatarImage src={company.logo_url ?? undefined} alt={company.name} />
          <AvatarFallback className="rounded-lg bg-primary/10 text-primary font-bold">
            {company.name.slice(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate font-semibold">{company.name}</h3>
            <TrustScoreBadge score={company.trust_score} />
          </div>
          <div className="mt-1 flex items-center gap-1 text-sm text-muted-foreground">
            <MapPin className="h-3.5 w-3.5" />
            {[company.city, countryName(company.country)]
              .filter(Boolean)
              .join(", ")}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <RatingStars rating={Number(company.rating_avg)} count={company.rating_count} />
            <VerificationBadge level={company.verification_level} />
          </div>
        </div>
      </div>
      {company.description && (
        <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">
          {company.description}
        </p>
      )}
      <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Briefcase className="h-3.5 w-3.5" />
          {company.completed_projects} completed projects
        </span>
        {company.year_founded && <span>Since {company.year_founded}</span>}
      </div>
    </Link>
  );
}
