import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  listShipmentsForOrder,
  requestShipment,
  updateShipmentStatus,
  SHIPMENT_FLOW,
  type ShipmentStatus,
} from "@/modules/logistics/api";
import { COUNTRIES, countryName } from "@/modules/core/countries";
import type { MarketplaceOrder } from "@/modules/orders/api";
import { toast } from "sonner";
import { ShieldCheck, Truck } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_LABELS: Record<ShipmentStatus, string> = {
  requested: "Requested",
  booked: "Booked",
  picked_up: "Picked up",
  in_transit: "In transit",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

export default function LogisticsCard({ order }: { order: MarketplaceOrder }) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [pickupAddress, setPickupAddress] = useState("");
  const [pickupCountry, setPickupCountry] = useState("");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [deliveryCountry, setDeliveryCountry] = useState("");
  const [insured, setInsured] = useState(true);

  const { data: shipments } = useQuery({
    queryKey: ["order-shipments", order.id],
    queryFn: () => listShipmentsForOrder(order.id),
  });

  const request = useMutation({
    mutationFn: () =>
      requestShipment({
        reference_id: order.id,
        counterpart_company_id: order.company_id,
        pickup_address: pickupAddress,
        pickup_country: pickupCountry,
        delivery_address: deliveryAddress,
        delivery_country: deliveryCountry,
        insured,
      }),
    onSuccess: () => {
      toast.success("Transport requested.");
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["order-shipments", order.id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const advance = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ShipmentStatus }) =>
      updateShipmentStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order-shipments", order.id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const active = shipments?.[0];
  const formValid =
    pickupAddress.trim() &&
    pickupCountry &&
    deliveryAddress.trim() &&
    deliveryCountry;

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Truck className="h-5 w-5 text-primary" />
          Transport
        </CardTitle>
        <CardDescription>
          Door-to-door transport with tracking and optional insurance — handled
          by the independent Baltic Bridge logistics module.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {active ? (
          <div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm">
                <div>
                  <span className="text-muted-foreground">From:</span>{" "}
                  {active.pickup_address}, {countryName(active.pickup_country)}
                </div>
                <div>
                  <span className="text-muted-foreground">To:</span>{" "}
                  {active.delivery_address}, {countryName(active.delivery_country)}
                </div>
                {active.tracking_code && (
                  <div>
                    <span className="text-muted-foreground">Tracking:</span>{" "}
                    <span className="font-mono">{active.tracking_code}</span>
                  </div>
                )}
              </div>
              <div className="flex flex-col items-end gap-1">
                <Badge className="capitalize">{STATUS_LABELS[active.status]}</Badge>
                {active.insured && (
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <ShieldCheck className="h-3 w-3" /> Transport insured
                  </span>
                )}
              </div>
            </div>

            {/* Progress */}
            {active.status !== "cancelled" && (
              <div className="mt-4 flex items-center gap-1">
                {SHIPMENT_FLOW.map((status, i) => {
                  const currentIndex = SHIPMENT_FLOW.indexOf(active.status);
                  return (
                    <div key={status} className="flex flex-1 flex-col items-center">
                      <div
                        className={cn(
                          "h-1.5 w-full rounded-full",
                          i <= currentIndex ? "bg-primary" : "bg-muted",
                        )}
                      />
                      <span className="mt-1 text-[10px] text-muted-foreground">
                        {STATUS_LABELS[status]}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Advance status (until provider integrations drive this) */}
            {active.status !== "delivered" && active.status !== "cancelled" && (
              <div className="mt-4 flex gap-2">
                {(() => {
                  const next =
                    SHIPMENT_FLOW[SHIPMENT_FLOW.indexOf(active.status) + 1];
                  return next ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => advance.mutate({ id: active.id, status: next })}
                      disabled={advance.isPending}
                    >
                      Mark as {STATUS_LABELS[next].toLowerCase()}
                    </Button>
                  ) : null;
                })()}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => advance.mutate({ id: active.id, status: "cancelled" })}
                  disabled={advance.isPending}
                >
                  Cancel transport
                </Button>
              </div>
            )}
          </div>
        ) : showForm ? (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Pickup address</Label>
                <Input value={pickupAddress} onChange={(e) => setPickupAddress(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Pickup country</Label>
                <Select value={pickupCountry} onValueChange={setPickupCountry}>
                  <SelectTrigger>
                    <SelectValue placeholder="Country" />
                  </SelectTrigger>
                  <SelectContent>
                    {COUNTRIES.map((c) => (
                      <SelectItem key={c.code} value={c.code}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Delivery address</Label>
                <Input value={deliveryAddress} onChange={(e) => setDeliveryAddress(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Delivery country</Label>
                <Select value={deliveryCountry} onValueChange={setDeliveryCountry}>
                  <SelectTrigger>
                    <SelectValue placeholder="Country" />
                  </SelectTrigger>
                  <SelectContent>
                    {COUNTRIES.map((c) => (
                      <SelectItem key={c.code} value={c.code}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="insured"
                checked={insured}
                onCheckedChange={(v) => setInsured(v === true)}
              />
              <Label htmlFor="insured" className="text-sm font-normal">
                Add transport insurance
              </Label>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={!formValid || request.isPending}
                onClick={() => request.mutate()}
              >
                {request.isPending ? "Requesting…" : "Request transport"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="outline" size="sm" onClick={() => setShowForm(true)}>
            <Truck className="mr-1.5 h-4 w-4" />
            Request transport for this order
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
