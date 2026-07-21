import { Link } from "react-router-dom";
import { MapPin, CalendarDays, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { countryName } from "@/modules/core/countries";
import { formatMoney } from "@/modules/core/types";
import type { Rfq } from "@/modules/rfq/types";
import { format } from "date-fns";

const STATUS_TONES: Record<string, string> = {
  published: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100",
  accepted: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100",
  withdrawn: "bg-muted text-muted-foreground",
  expired: "bg-muted text-muted-foreground",
  draft: "bg-muted text-muted-foreground",
};

export default function RfqCard({ rfq }: { rfq: Rfq }) {
  const budget =
    rfq.budget_min || rfq.budget_max
      ? [
          rfq.budget_min ? formatMoney(Number(rfq.budget_min), rfq.currency) : null,
          rfq.budget_max ? formatMoney(Number(rfq.budget_max), rfq.currency) : null,
        ]
          .filter(Boolean)
          .join(" – ")
      : null;

  return (
    <Link to={`/rfq/${rfq.id}`} className="card-elevated block p-5">
      <div className="flex flex-wrap items-center gap-2">
        {rfq.verticals && (
          <Badge variant="outline">{rfq.verticals.name}</Badge>
        )}
        {rfq.categories && (
          <Badge variant="secondary">{rfq.categories.name}</Badge>
        )}
        <Badge className={`${STATUS_TONES[rfq.status] ?? ""} border-0 capitalize`}>
          {rfq.status}
        </Badge>
      </div>
      <h3 className="mt-2 font-semibold">{rfq.title}</h3>
      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
        {rfq.description}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <MapPin className="h-3.5 w-3.5" />
          {[rfq.city, countryName(rfq.country)].filter(Boolean).join(", ")}
        </span>
        {budget && (
          <span className="inline-flex items-center gap-1">
            <Wallet className="h-3.5 w-3.5" />
            {budget}
          </span>
        )}
        {rfq.deadline && (
          <span className="inline-flex items-center gap-1">
            <CalendarDays className="h-3.5 w-3.5" />
            Deadline {format(new Date(rfq.deadline), "d MMM yyyy")}
          </span>
        )}
      </div>
    </Link>
  );
}
