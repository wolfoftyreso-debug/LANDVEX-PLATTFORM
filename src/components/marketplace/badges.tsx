import { Badge } from "@/components/ui/badge";
import { ShieldCheck, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import type { VerificationLevel } from "@/modules/core/types";

const LEVEL_STYLES: Record<VerificationLevel, string> = {
  unverified: "bg-muted text-muted-foreground",
  bronze: "bg-amber-800/90 text-white",
  silver: "bg-slate-400 text-slate-950",
  gold: "bg-amber-400 text-amber-950",
  platinum: "bg-gradient-to-r from-slate-200 to-cyan-200 text-slate-900",
};

const LEVEL_LABELS: Record<VerificationLevel, string> = {
  unverified: "Not verified",
  bronze: "Bronze verified",
  silver: "Silver verified",
  gold: "Gold verified",
  platinum: "Platinum verified",
};

export function VerificationBadge({
  level,
  className,
}: {
  level: VerificationLevel;
  className?: string;
}) {
  if (level === "unverified") return null;
  return (
    <Badge className={cn(LEVEL_STYLES[level], "gap-1 border-0", className)}>
      <ShieldCheck className="h-3 w-3" />
      {LEVEL_LABELS[level]}
    </Badge>
  );
}

export function TrustScoreBadge({
  score,
  className,
}: {
  score: number;
  className?: string;
}) {
  const tone =
    score >= 70
      ? "bg-emerald-600 text-white"
      : score >= 40
        ? "bg-amber-500 text-amber-950"
        : "bg-muted text-muted-foreground";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
        tone,
        className,
      )}
      title="Baltic Bridge Trust Score (0–100), calculated from verification, reviews, completed projects and responsiveness"
    >
      <ShieldCheck className="h-3 w-3" />
      {Math.round(score)}
    </span>
  );
}

export function RatingStars({
  rating,
  count,
  className,
}: {
  rating: number;
  count?: number;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1 text-sm", className)}>
      <span className="flex">
        {[1, 2, 3, 4, 5].map((i) => (
          <Star
            key={i}
            className={cn(
              "h-4 w-4",
              i <= Math.round(rating)
                ? "fill-accent text-accent"
                : "text-muted-foreground/40",
            )}
          />
        ))}
      </span>
      <span className="font-medium">{rating > 0 ? rating.toFixed(1) : "New"}</span>
      {count !== undefined && count > 0 && (
        <span className="text-muted-foreground">({count})</span>
      )}
    </span>
  );
}
