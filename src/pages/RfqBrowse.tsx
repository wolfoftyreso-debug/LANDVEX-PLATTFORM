import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import RfqCard from "@/components/marketplace/RfqCard";
import EmptyState from "@/components/marketplace/EmptyState";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { listOpenRfqs } from "@/modules/rfq/api";
import { listVerticals } from "@/modules/marketplace/api";
import { COUNTRIES } from "@/modules/core/countries";
import { FileText } from "lucide-react";

const ALL = "all";

export default function RfqBrowse() {
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [verticalId, setVerticalId] = useState(ALL);
  const [country, setCountry] = useState(ALL);

  const { data: verticals } = useQuery({ queryKey: ["verticals"], queryFn: listVerticals });
  const { data: rfqs, isLoading } = useQuery({
    queryKey: ["open-rfqs", verticalId, country],
    queryFn: () =>
      listOpenRfqs({
        verticalId: verticalId === ALL ? undefined : verticalId,
        country: country === ALL ? undefined : country,
      }),
    enabled: !!user,
  });

  return (
    <SiteLayout>
      <div className="border-b bg-card">
        <div className="container mx-auto px-4 py-10">
          <h1 className="text-3xl font-bold">Open requests</h1>
          <p className="mt-1 text-muted-foreground">
            Customer requests waiting for quotes. Respond quickly — response time
            affects your trust score.
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {!loading && !user ? (
          <EmptyState
            icon={FileText}
            title="Sign in to browse requests"
            description="Company accounts can browse and respond to open customer requests."
            action={<Button onClick={() => navigate("/auth?next=/rfqs")}>Sign in</Button>}
          />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 md:max-w-lg">
              <Select value={verticalId} onValueChange={setVerticalId}>
                <SelectTrigger>
                  <SelectValue placeholder="Marketplace" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All marketplaces</SelectItem>
                  {verticals?.map((v) => (
                    <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={country} onValueChange={setCountry}>
                <SelectTrigger>
                  <SelectValue placeholder="Country" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All countries</SelectItem>
                  {COUNTRIES.map((c) => (
                    <SelectItem key={c.code} value={c.code}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="mt-6">
              {isLoading ? (
                <p className="text-muted-foreground">Loading requests…</p>
              ) : rfqs && rfqs.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {rfqs.map((rfq) => (
                    <RfqCard key={rfq.id} rfq={rfq} />
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={FileText}
                  title="No open requests right now"
                  description="New customer requests appear here as soon as they are published."
                />
              )}
            </div>
          </>
        )}
      </div>
    </SiteLayout>
  );
}
