import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import EmptyState from "@/components/marketplace/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/useAuth";
import { getOrder, updateOrderStatus } from "@/modules/orders/api";
import { getMyCompany } from "@/modules/companies/api";
import { getOrCreateConversation } from "@/modules/messaging/api";
import { createReview } from "@/modules/reviews/api";
import { formatMoney } from "@/modules/core/types";
import type { OrderStatus } from "@/modules/core/types";
import { toast } from "sonner";
import { format } from "date-fns";
import { MessagesSquare, Package, Star } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";

const STATUS_FLOW: OrderStatus[] = ["created", "in_progress", "delivered", "completed"];

const STATUS_LABELS: Record<OrderStatus, string> = {
  created: "Order created",
  in_progress: "Work in progress",
  delivered: "Delivered",
  completed: "Completed",
  disputed: "Disputed",
  cancelled: "Cancelled",
};

function StarPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm">{label}</span>
      <span className="flex">
        {[1, 2, 3, 4, 5].map((i) => (
          <button key={i} type="button" onClick={() => onChange(i)} aria-label={`${label} ${i} of 5`}>
            <Star
              className={cn(
                "h-5 w-5",
                i <= value ? "fill-accent text-accent" : "text-muted-foreground/40",
              )}
            />
          </button>
        ))}
      </span>
    </div>
  );
}

export default function OrderDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const { data: order, isLoading } = useQuery({
    queryKey: ["order", id],
    queryFn: () => getOrder(id!),
    enabled: !!id && !!user,
  });

  const { data: myCompany } = useQuery({
    queryKey: ["my-company"],
    queryFn: getMyCompany,
    enabled: !!user,
  });

  const isCustomer = !!order && !!user && order.customer_id === user.id;
  const isCompanySide = !!order && !!myCompany && order.company_id === myCompany.id;
  const hasReview = !!order?.reviews && order.reviews.length > 0;

  const [ratings, setRatings] = useState({
    overall: 0,
    communication: 0,
    quality: 0,
    price: 0,
    delivery: 0,
    professionalism: 0,
  });
  const [comment, setComment] = useState("");
  const [recommend, setRecommend] = useState(true);

  const setStatus = useMutation({
    mutationFn: (status: OrderStatus) => updateOrderStatus(id!, status),
    onSuccess: () => {
      toast.success("Order status updated.");
      queryClient.invalidateQueries({ queryKey: ["order", id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const message = useMutation({
    mutationFn: () =>
      getOrCreateConversation({
        companyId: order!.company_id,
        customerId: order!.customer_id,
        rfqId: order!.rfq_id,
        orderId: order!.id,
      }),
    onSuccess: (conversation) =>
      navigate(`/messages?conversation=${conversation.id}`),
    onError: (error: Error) => toast.error(error.message),
  });

  const review = useMutation({
    mutationFn: () =>
      createReview({
        order_id: order!.id,
        company_id: order!.company_id,
        rating_overall: ratings.overall,
        rating_communication: ratings.communication || undefined,
        rating_quality: ratings.quality || undefined,
        rating_price: ratings.price || undefined,
        rating_delivery: ratings.delivery || undefined,
        rating_professionalism: ratings.professionalism || undefined,
        would_recommend: recommend,
        comment: comment || undefined,
      }),
    onSuccess: () => {
      toast.success("Thank you! Your verified review is now public.");
      queryClient.invalidateQueries({ queryKey: ["order", id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (isLoading) {
    return (
      <SiteLayout>
        <div className="container mx-auto px-4 py-16 text-muted-foreground">Loading order…</div>
      </SiteLayout>
    );
  }

  if (!order) {
    return (
      <SiteLayout>
        <div className="container mx-auto px-4 py-16">
          <EmptyState
            icon={Package}
            title="Order not found"
            description="Sign in with the account that placed or received this order."
          />
        </div>
      </SiteLayout>
    );
  }

  const currentIndex = STATUS_FLOW.indexOf(order.status);

  return (
    <SiteLayout>
      <div className="container mx-auto max-w-3xl px-4 py-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">{order.rfqs?.title ?? "Order"}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Order placed {format(new Date(order.created_at), "d MMM yyyy")} ·{" "}
              {order.companies && (
                <Link to={`/company/${order.companies.slug}`} className="text-primary hover:underline">
                  {order.companies.name}
                </Link>
              )}
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold">
              {formatMoney(Number(order.amount), order.currency)}
            </div>
            <Badge className="capitalize">{STATUS_LABELS[order.status]}</Badge>
          </div>
        </div>

        {/* Status timeline */}
        {currentIndex >= 0 && (
          <div className="card-elevated mt-6 p-6">
            <div className="flex items-center">
              {STATUS_FLOW.map((status, i) => (
                <div key={status} className="flex flex-1 items-center last:flex-none">
                  <div className="flex flex-col items-center">
                    <div
                      className={cn(
                        "flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold",
                        i <= currentIndex
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {i + 1}
                    </div>
                    <span className="mt-1 whitespace-nowrap text-[10px] text-muted-foreground sm:text-xs">
                      {STATUS_LABELS[status]}
                    </span>
                  </div>
                  {i < STATUS_FLOW.length - 1 && (
                    <div
                      className={cn(
                        "mx-1 h-0.5 flex-1 -translate-y-2.5",
                        i < currentIndex ? "bg-primary" : "bg-muted",
                      )}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex flex-wrap gap-3">
          {(isCustomer || isCompanySide) && (
            <Button
              variant="outline"
              onClick={() => message.mutate()}
              disabled={message.isPending}
            >
              <MessagesSquare className="mr-1.5 h-4 w-4" />
              {isCustomer ? "Message the company" : "Message the customer"}
            </Button>
          )}
          {isCompanySide && order.status === "created" && (
            <Button onClick={() => setStatus.mutate("in_progress")} disabled={setStatus.isPending}>
              Start work
            </Button>
          )}
          {isCompanySide && order.status === "in_progress" && (
            <Button onClick={() => setStatus.mutate("delivered")} disabled={setStatus.isPending}>
              Mark as delivered
            </Button>
          )}
          {isCustomer && order.status === "delivered" && (
            <Button onClick={() => setStatus.mutate("completed")} disabled={setStatus.isPending}>
              Approve & complete order
            </Button>
          )}
          {(isCustomer || isCompanySide) &&
            !["completed", "cancelled", "disputed"].includes(order.status) && (
              <Button
                variant="outline"
                onClick={() => setStatus.mutate("disputed")}
                disabled={setStatus.isPending}
              >
                Open dispute
              </Button>
            )}
        </div>

        {/* Review */}
        {isCustomer && order.status === "completed" && !hasReview && (
          <Card className="mt-8">
            <CardHeader>
              <CardTitle>Review {order.companies?.name}</CardTitle>
              <CardDescription>
                Your review is marked as verified and directly affects the
                company's trust score.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <StarPicker
                label="Overall *"
                value={ratings.overall}
                onChange={(v) => setRatings((r) => ({ ...r, overall: v }))}
              />
              <StarPicker
                label="Communication"
                value={ratings.communication}
                onChange={(v) => setRatings((r) => ({ ...r, communication: v }))}
              />
              <StarPicker
                label="Quality"
                value={ratings.quality}
                onChange={(v) => setRatings((r) => ({ ...r, quality: v }))}
              />
              <StarPicker
                label="Price"
                value={ratings.price}
                onChange={(v) => setRatings((r) => ({ ...r, price: v }))}
              />
              <StarPicker
                label="Delivery"
                value={ratings.delivery}
                onChange={(v) => setRatings((r) => ({ ...r, delivery: v }))}
              />
              <StarPicker
                label="Professionalism"
                value={ratings.professionalism}
                onChange={(v) => setRatings((r) => ({ ...r, professionalism: v }))}
              />
              <Textarea
                rows={4}
                placeholder="Tell others about your experience…"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <div className="flex items-center gap-2">
                <Checkbox
                  id="recommend"
                  checked={recommend}
                  onCheckedChange={(v) => setRecommend(v === true)}
                />
                <Label htmlFor="recommend" className="text-sm font-normal">
                  I would recommend this company
                </Label>
              </div>
              <Button
                disabled={ratings.overall === 0 || review.isPending}
                onClick={() => review.mutate()}
              >
                {review.isPending ? "Publishing…" : "Publish verified review"}
              </Button>
            </CardContent>
          </Card>
        )}

        {hasReview && (
          <p className="mt-6 text-sm text-muted-foreground">
            ✓ A verified review has been published for this order.
          </p>
        )}
      </div>
    </SiteLayout>
  );
}
