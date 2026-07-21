import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import EmptyState from "@/components/marketplace/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/useAuth";
import {
  isAdmin,
  listVerificationQueue,
  reviewVerification,
} from "@/modules/verification/api";
import { countryName } from "@/modules/core/countries";
import { toast } from "sonner";
import { format } from "date-fns";
import { CheckCircle2, ShieldQuestion, XCircle } from "lucide-react";

export default function AdminBackOffice() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, loading } = useAuth();
  const [rejectNotes, setRejectNotes] = useState<Record<string, string>>({});

  const { data: admin, isLoading: adminLoading } = useQuery({
    queryKey: ["is-admin"],
    queryFn: isAdmin,
    enabled: !!user,
  });

  const { data: queue } = useQuery({
    queryKey: ["verification-queue"],
    queryFn: listVerificationQueue,
    enabled: admin === true,
  });

  const review = useMutation({
    mutationFn: ({ id, approve, notes }: { id: string; approve: boolean; notes?: string }) =>
      reviewVerification(id, approve, notes),
    onSuccess: (_, vars) => {
      toast.success(vars.approve ? "Request approved." : "Request rejected.");
      queryClient.invalidateQueries({ queryKey: ["verification-queue"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (!loading && !user) {
    navigate("/auth?next=/admin");
    return null;
  }

  if (!adminLoading && admin === false) {
    return (
      <SiteLayout>
        <div className="container mx-auto px-4 py-16">
          <EmptyState
            icon={ShieldQuestion}
            title="Administrators only"
            description="This back office requires a platform administrator account."
          />
        </div>
      </SiteLayout>
    );
  }

  return (
    <SiteLayout>
      <div className="container mx-auto max-w-4xl px-4 py-10">
        <h1 className="text-3xl font-bold">Back office</h1>
        <p className="mt-1 text-muted-foreground">
          Verification queue — approvals immediately update the company's level
          and trust score.
        </p>

        <div className="mt-8 space-y-4">
          {queue && queue.length > 0 ? (
            queue.map((request) => (
              <div key={request.id} className="card-elevated p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/company/${request.company_slug}`}
                        className="font-semibold text-primary hover:underline"
                      >
                        {request.company_name}
                      </Link>
                      <Badge variant="outline">
                        {countryName(request.company_country ?? "")}
                      </Badge>
                      <Badge className="capitalize">{request.requested_level}</Badge>
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      Applied {format(new Date(request.created_at), "d MMM yyyy")}
                      {request.vat_number && <> · VAT: {request.vat_number}</>}
                      {request.org_number && <> · Org: {request.org_number}</>}
                    </div>
                    {request.documents.length > 0 && (
                      <div className="mt-2 text-sm">
                        <span className="text-muted-foreground">Documentation:</span>{" "}
                        {request.documents.map((d) => d.name).join("; ")}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() =>
                          review.mutate({ id: request.id, approve: true })
                        }
                        disabled={review.isPending}
                      >
                        <CheckCircle2 className="mr-1 h-4 w-4" /> Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() =>
                          review.mutate({
                            id: request.id,
                            approve: false,
                            notes: rejectNotes[request.id],
                          })
                        }
                        disabled={review.isPending}
                      >
                        <XCircle className="mr-1 h-4 w-4" /> Reject
                      </Button>
                    </div>
                    <Textarea
                      rows={1}
                      className="w-64 text-xs"
                      placeholder="Rejection reason (optional)"
                      value={rejectNotes[request.id] ?? ""}
                      onChange={(e) =>
                        setRejectNotes((n) => ({ ...n, [request.id]: e.target.value }))
                      }
                    />
                  </div>
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              icon={CheckCircle2}
              title="Queue is empty"
              description="No pending verification requests right now."
            />
          )}
        </div>
      </div>
    </SiteLayout>
  );
}
