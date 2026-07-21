import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { VerificationBadge } from "@/components/marketplace/badges";
import {
  listCompanyVerificationRequests,
  nextLevel,
  requestVerification,
} from "@/modules/verification/api";
import type { Company } from "@/modules/companies/types";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";

const LEVEL_REQUIREMENTS: Record<string, string> = {
  bronze: "Confirm identity and provide organization number.",
  silver: "Bronze + verified VAT number and proof of insurance.",
  gold: "Silver + trade licenses, references from 5 completed orders.",
  platinum: "Gold + on-site audit and financial health check.",
};

export default function VerificationCard({ company }: { company: Company }) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data: requests } = useQuery({
    queryKey: ["verification-requests", company.id],
    queryFn: () => listCompanyVerificationRequests(company.id),
  });

  const pending = requests?.find((r) => r.status === "pending");
  const target = nextLevel(company.verification_level);

  const apply = useMutation({
    mutationFn: () =>
      requestVerification(company.id, target!, notes ? [{ name: notes }] : []),
    onSuccess: () => {
      toast.success("Verification request submitted for review.");
      setShowForm(false);
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["verification-requests", company.id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldCheck className="h-5 w-5 text-primary" />
          Verification
        </CardTitle>
        <CardDescription>
          Higher levels are harder to obtain and give higher visibility in search.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Current level:</span>
          {company.verification_level === "unverified" ? (
            <Badge variant="outline">Not verified</Badge>
          ) : (
            <VerificationBadge level={company.verification_level} />
          )}
        </div>

        {pending ? (
          <p className="mt-3 text-sm text-muted-foreground">
            Your <strong className="capitalize">{pending.requested_level}</strong>{" "}
            request is under review.
          </p>
        ) : target ? (
          <div className="mt-3">
            <p className="text-sm text-muted-foreground">
              Next level: <strong className="capitalize">{target}</strong> —{" "}
              {LEVEL_REQUIREMENTS[target]}
            </p>
            {showForm ? (
              <div className="mt-3 space-y-2">
                <Textarea
                  rows={3}
                  placeholder="Describe your documentation (links to certificates, licenses, insurance…)"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => apply.mutate()} disabled={apply.isPending}>
                    Submit request
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button size="sm" className="mt-3" onClick={() => setShowForm(true)}>
                Apply for <span className="ml-1 capitalize">{target}</span>
              </Button>
            )}
          </div>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            You have reached the highest verification level. 🏆
          </p>
        )}
      </CardContent>
    </Card>
  );
}
