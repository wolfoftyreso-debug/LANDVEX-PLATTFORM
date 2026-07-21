import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getOrderPayment, payOrderEscrow } from "@/modules/payments/api";
import { formatMoney } from "@/modules/core/types";
import type { MarketplaceOrder } from "@/modules/orders/api";
import { toast } from "sonner";
import { CheckCircle2, Landmark, Lock, ShieldCheck } from "lucide-react";

export default function PaymentCard({
  order,
  isCustomer,
}: {
  order: MarketplaceOrder;
  isCustomer: boolean;
}) {
  const queryClient = useQueryClient();

  const { data: payment } = useQuery({
    queryKey: ["order-payment", order.id],
    queryFn: () => getOrderPayment(order.id),
  });

  const pay = useMutation({
    mutationFn: () => payOrderEscrow(order.id),
    onSuccess: () => {
      toast.success("Payment secured in escrow. It is released when you approve the completed order.");
      queryClient.invalidateQueries({ queryKey: ["order-payment", order.id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (!payment) return null;

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Landmark className="h-5 w-5 text-primary" />
          Payment
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-2xl font-bold">
            {formatMoney(Number(payment.amount), payment.currency)}
          </div>
          {payment.status === "pending" && (
            <Badge variant="outline" className="gap-1">
              <Lock className="h-3 w-3" /> Awaiting payment
            </Badge>
          )}
          {payment.status === "held_in_escrow" && (
            <Badge className="gap-1 border-0 bg-amber-500 text-amber-950">
              <ShieldCheck className="h-3 w-3" /> Held in escrow
            </Badge>
          )}
          {payment.status === "released" && (
            <Badge className="gap-1 border-0 bg-emerald-600 text-white">
              <CheckCircle2 className="h-3 w-3" /> Released to company
            </Badge>
          )}
          {payment.status === "refunded" && (
            <Badge variant="secondary">Refunded</Badge>
          )}
        </div>

        {payment.status === "pending" && isCustomer && (
          <div className="mt-4">
            <p className="text-sm text-muted-foreground">
              Secure the full amount in escrow. The company only receives the
              money after you approve the completed work — that protection is
              part of every Baltic Bridge order.
            </p>
            <Button className="mt-3" onClick={() => pay.mutate()} disabled={pay.isPending}>
              <ShieldCheck className="mr-1.5 h-4 w-4" />
              {pay.isPending ? "Securing…" : "Pay into escrow"}
            </Button>
          </div>
        )}
        {payment.status === "pending" && !isCustomer && (
          <p className="mt-3 text-sm text-muted-foreground">
            Waiting for the customer to secure the amount in escrow.
          </p>
        )}
        {payment.status === "held_in_escrow" && (
          <p className="mt-3 text-sm text-muted-foreground">
            Funds are held safely and released automatically when the customer
            approves the completed order.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
