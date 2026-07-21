import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import RfqCard from "@/components/marketplace/RfqCard";
import EmptyState from "@/components/marketplace/EmptyState";
import { TrustScoreBadge, VerificationBadge } from "@/components/marketplace/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/useAuth";
import { getMyCompany } from "@/modules/companies/api";
import { listMyRfqs } from "@/modules/rfq/api";
import { listCompanyOffers } from "@/modules/offers/api";
import { listCompanyOrders, listMyCustomerOrders } from "@/modules/orders/api";
import { formatMoney } from "@/modules/core/types";
import { format } from "date-fns";
import {
  Building2,
  FileText,
  Package,
  Send,
  Star,
  ArrowRight,
} from "lucide-react";

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, loading } = useAuth();

  const { data: myCompany, isLoading: companyLoading } = useQuery({
    queryKey: ["my-company"],
    queryFn: getMyCompany,
    enabled: !!user,
  });

  const { data: myRfqs } = useQuery({
    queryKey: ["my-rfqs"],
    queryFn: listMyRfqs,
    enabled: !!user,
  });

  const { data: customerOrders } = useQuery({
    queryKey: ["my-customer-orders"],
    queryFn: listMyCustomerOrders,
    enabled: !!user,
  });

  const { data: companyOffers } = useQuery({
    queryKey: ["company-offers", myCompany?.id],
    queryFn: () => listCompanyOffers(myCompany!.id),
    enabled: !!myCompany,
  });

  const { data: companyOrders } = useQuery({
    queryKey: ["company-orders", myCompany?.id],
    queryFn: () => listCompanyOrders(myCompany!.id),
    enabled: !!myCompany,
  });

  if (!loading && !user) {
    navigate("/auth?next=/dashboard");
    return null;
  }

  return (
    <SiteLayout>
      <div className="container mx-auto px-4 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Dashboard</h1>
            <p className="mt-1 text-muted-foreground">{user?.email}</p>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => navigate("/rfq/new")}>
              <FileText className="mr-1.5 h-4 w-4" /> New request
            </Button>
            {!myCompany && !companyLoading && (
              <Button variant="outline" onClick={() => navigate("/company/register")}>
                <Building2 className="mr-1.5 h-4 w-4" /> List your company
              </Button>
            )}
          </div>
        </div>

        {/* Company panel */}
        {myCompany && (
          <div className="card-elevated mt-6 flex flex-wrap items-center justify-between gap-4 p-5">
            <div className="flex items-center gap-3">
              <Building2 className="h-8 w-8 text-primary" />
              <div>
                <div className="flex items-center gap-2 font-semibold">
                  {myCompany.name}
                  <TrustScoreBadge score={Number(myCompany.trust_score)} />
                  <VerificationBadge level={myCompany.verification_level} />
                </div>
                <Link
                  to={`/company/${myCompany.slug}`}
                  className="text-sm text-primary hover:underline"
                >
                  View public profile
                </Link>
              </div>
            </div>
            <Button variant="outline" onClick={() => navigate("/rfqs")}>
              Browse open requests <ArrowRight className="ml-1.5 h-4 w-4" />
            </Button>
          </div>
        )}

        <Tabs defaultValue={myCompany ? "leads" : "requests"} className="mt-8">
          <TabsList>
            <TabsTrigger value="requests">My requests</TabsTrigger>
            <TabsTrigger value="orders">My orders</TabsTrigger>
            {myCompany && <TabsTrigger value="leads">Sent quotes</TabsTrigger>}
            {myCompany && <TabsTrigger value="company-orders">Company orders</TabsTrigger>}
          </TabsList>

          {/* Customer: RFQs */}
          <TabsContent value="requests" className="mt-6">
            {myRfqs && myRfqs.length > 0 ? (
              <div className="grid gap-4 md:grid-cols-2">
                {myRfqs.map((rfq) => (
                  <RfqCard key={rfq.id} rfq={rfq} />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={FileText}
                title="No requests yet"
                description="Post your first request and receive quotes from verified companies."
                action={<Button onClick={() => navigate("/rfq/new")}>Request quotes</Button>}
              />
            )}
          </TabsContent>

          {/* Customer: orders */}
          <TabsContent value="orders" className="mt-6">
            {customerOrders && customerOrders.length > 0 ? (
              <div className="space-y-3">
                {customerOrders.map((order) => (
                  <Link
                    key={order.id}
                    to={`/order/${order.id}`}
                    className="card-elevated flex items-center justify-between gap-4 p-4"
                  >
                    <div>
                      <div className="font-semibold">{order.rfqs?.title}</div>
                      <div className="text-sm text-muted-foreground">
                        {order.companies?.name} · {format(new Date(order.created_at), "d MMM yyyy")}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {order.status === "completed" && (!order.reviews || order.reviews.length === 0) && (
                        <Badge variant="secondary" className="gap-1">
                          <Star className="h-3 w-3" /> Review pending
                        </Badge>
                      )}
                      <Badge className="capitalize">{order.status.replace("_", " ")}</Badge>
                      <span className="font-bold">
                        {formatMoney(Number(order.amount), order.currency)}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Package}
                title="No orders yet"
                description="When you accept a quote, the order appears here."
              />
            )}
          </TabsContent>

          {/* Company: sent quotes */}
          {myCompany && (
            <TabsContent value="leads" className="mt-6">
              {companyOffers && companyOffers.length > 0 ? (
                <div className="space-y-3">
                  {companyOffers.map((offer) => (
                    <Link
                      key={offer.id}
                      to={`/rfq/${offer.rfq_id}`}
                      className="card-elevated flex items-center justify-between gap-4 p-4"
                    >
                      <div>
                        <div className="font-semibold">{offer.rfqs?.title}</div>
                        <div className="text-sm text-muted-foreground">
                          Sent {format(new Date(offer.created_at), "d MMM yyyy")}
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge variant="outline" className="capitalize">{offer.status}</Badge>
                        <span className="font-bold">
                          {formatMoney(Number(offer.price), offer.currency)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={Send}
                  title="No quotes sent yet"
                  description="Browse open requests and send your first quote."
                  action={<Button onClick={() => navigate("/rfqs")}>Browse requests</Button>}
                />
              )}
            </TabsContent>
          )}

          {/* Company: orders */}
          {myCompany && (
            <TabsContent value="company-orders" className="mt-6">
              {companyOrders && companyOrders.length > 0 ? (
                <div className="space-y-3">
                  {companyOrders.map((order) => (
                    <Link
                      key={order.id}
                      to={`/order/${order.id}`}
                      className="card-elevated flex items-center justify-between gap-4 p-4"
                    >
                      <div>
                        <div className="font-semibold">{order.rfqs?.title}</div>
                        <div className="text-sm text-muted-foreground">
                          {format(new Date(order.created_at), "d MMM yyyy")}
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge className="capitalize">{order.status.replace("_", " ")}</Badge>
                        <span className="font-bold">
                          {formatMoney(Number(order.amount), order.currency)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={Package}
                  title="No orders yet"
                  description="When a customer accepts your quote, the order appears here."
                />
              )}
            </TabsContent>
          )}
        </Tabs>
      </div>
    </SiteLayout>
  );
}
