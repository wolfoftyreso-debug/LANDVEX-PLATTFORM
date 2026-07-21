import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import EmptyState from "@/components/marketplace/EmptyState";
import {
  RatingStars,
  TrustScoreBadge,
  VerificationBadge,
} from "@/components/marketplace/badges";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/useAuth";
import { getRfq, withdrawRfq } from "@/modules/rfq/api";
import {
  acceptOffer,
  listOffersForRfq,
  submitOffer,
} from "@/modules/offers/api";
import { getMyCompany } from "@/modules/companies/api";
import { getOrCreateConversation } from "@/modules/messaging/api";
import { verticalConfig } from "@/modules/marketplace/config";
import { countryName, languageName } from "@/modules/core/countries";
import { formatMoney } from "@/modules/core/types";
import type { VerificationLevel } from "@/modules/core/types";
import { toast } from "sonner";
import { format } from "date-fns";
import {
  CalendarDays,
  FileQuestion,
  MapPin,
  MessagesSquare,
  Send,
  Wallet,
  CheckCircle2,
} from "lucide-react";

export default function RfqDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [offerPrice, setOfferPrice] = useState("");
  const [offerDescription, setOfferDescription] = useState("");
  const [offerDays, setOfferDays] = useState("");

  const { data: rfq, isLoading } = useQuery({
    queryKey: ["rfq", id],
    queryFn: () => getRfq(id!),
    enabled: !!id,
  });

  const isOwner = !!user && !!rfq && rfq.customer_id === user.id;

  const { data: myCompany } = useQuery({
    queryKey: ["my-company"],
    queryFn: getMyCompany,
    enabled: !!user,
  });

  const { data: offers } = useQuery({
    queryKey: ["rfq-offers", id],
    queryFn: () => listOffersForRfq(id!),
    enabled: !!id && !!user && (isOwner || !!myCompany),
  });

  const myOffer = offers?.find((o) => o.company_id === myCompany?.id);
  const canQuote =
    !!myCompany && !isOwner && rfq?.status === "published" && !myOffer;

  const sendOffer = useMutation({
    mutationFn: () =>
      submitOffer({
        rfq_id: id!,
        company_id: myCompany!.id,
        price: Number(offerPrice),
        currency: rfq!.currency,
        description: offerDescription,
        estimated_days: offerDays ? Number(offerDays) : null,
      }),
    onSuccess: () => {
      toast.success("Your quote has been sent to the customer.");
      queryClient.invalidateQueries({ queryKey: ["rfq-offers", id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const accept = useMutation({
    mutationFn: (offerId: string) => acceptOffer(offerId),
    onSuccess: (orderId) => {
      toast.success("Offer accepted — your order has been created.");
      navigate(`/order/${orderId}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const message = useMutation({
    mutationFn: (companyId: string) =>
      getOrCreateConversation({
        companyId,
        customerId: rfq!.customer_id,
        rfqId: rfq!.id,
      }),
    onSuccess: (conversation) =>
      navigate(`/messages?conversation=${conversation.id}`),
    onError: (error: Error) => toast.error(error.message),
  });

  const withdraw = useMutation({
    mutationFn: () => withdrawRfq(id!),
    onSuccess: () => {
      toast.success("Request withdrawn.");
      queryClient.invalidateQueries({ queryKey: ["rfq", id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (isLoading) {
    return (
      <SiteLayout>
        <div className="container mx-auto px-4 py-16 text-muted-foreground">Loading request…</div>
      </SiteLayout>
    );
  }

  if (!rfq) {
    return (
      <SiteLayout>
        <div className="container mx-auto px-4 py-16">
          <EmptyState
            icon={FileQuestion}
            title="Request not found"
            description="It may have been withdrawn, or you may not have access."
          />
        </div>
      </SiteLayout>
    );
  }

  const uiConfig = rfq.verticals ? verticalConfig(rfq.verticals.slug) : undefined;
  const budget =
    rfq.budget_min || rfq.budget_max
      ? [
          rfq.budget_min ? formatMoney(Number(rfq.budget_min), rfq.currency) : null,
          rfq.budget_max ? formatMoney(Number(rfq.budget_max), rfq.currency) : null,
        ]
          .filter(Boolean)
          .join(" – ")
      : "Not specified";

  return (
    <SiteLayout>
      <div className="container mx-auto max-w-4xl px-4 py-10">
        <div className="flex flex-wrap items-center gap-2">
          {rfq.verticals && <Badge variant="outline">{rfq.verticals.name}</Badge>}
          {rfq.categories && <Badge variant="secondary">{rfq.categories.name}</Badge>}
          <Badge className="capitalize">{rfq.status}</Badge>
        </div>
        <h1 className="mt-3 text-3xl font-bold">{rfq.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <MapPin className="h-4 w-4" />
            {[rfq.city, countryName(rfq.country)].filter(Boolean).join(", ")}
          </span>
          <span className="inline-flex items-center gap-1">
            <Wallet className="h-4 w-4" /> {budget}
          </span>
          {rfq.deadline && (
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="h-4 w-4" />
              Deadline {format(new Date(rfq.deadline), "d MMM yyyy")}
            </span>
          )}
          {rfq.preferred_language && (
            <span>Preferred language: {languageName(rfq.preferred_language)}</span>
          )}
        </div>

        <div className="card-elevated mt-6 p-6">
          <h2 className="font-semibold">Description</h2>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
            {rfq.description}
          </p>

          {Object.keys(rfq.metadata ?? {}).length > 0 && (
            <div className="mt-4 grid gap-2 border-t pt-4 sm:grid-cols-2">
              {Object.entries(rfq.metadata).map(([key, value]) => {
                if (!value) return null;
                const field = uiConfig?.metadataFields.find((f) => f.key === key);
                return (
                  <div key={key} className="text-sm">
                    <span className="text-muted-foreground">
                      {field?.label ?? key}:
                    </span>{" "}
                    <span className="font-medium">
                      {field?.options?.find((o) => o.value === value)?.label ?? value}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {rfq.rfq_images && rfq.rfq_images.length > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {rfq.rfq_images.map((img) => (
                <img
                  key={img.id}
                  src={img.image_url}
                  alt="Project"
                  className="h-32 w-full rounded-md object-cover"
                />
              ))}
            </div>
          )}
        </div>

        {isOwner && rfq.status === "published" && (
          <div className="mt-4 flex justify-end">
            <Button variant="outline" onClick={() => withdraw.mutate()} disabled={withdraw.isPending}>
              Withdraw request
            </Button>
          </div>
        )}

        {/* Offers — visible to the RFQ owner */}
        {isOwner && (
          <div className="mt-8">
            <h2 className="text-xl font-bold">
              Quotes received {offers && offers.length > 0 && `(${offers.length})`}
            </h2>
            {offers && offers.length > 0 ? (
              <div className="mt-4 space-y-4">
                {offers.map((offer) => (
                  <div key={offer.id} className="card-elevated p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <Link
                        to={`/company/${offer.companies?.slug}`}
                        className="flex items-center gap-3"
                      >
                        <Avatar className="h-11 w-11 rounded-lg">
                          <AvatarImage src={offer.companies?.logo_url ?? undefined} />
                          <AvatarFallback className="rounded-lg bg-primary/10 font-bold text-primary">
                            {offer.companies?.name?.slice(0, 2).toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <div className="flex items-center gap-2 font-semibold">
                            {offer.companies?.name}
                            {offer.companies && (
                              <TrustScoreBadge score={Number(offer.companies.trust_score)} />
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            {offer.companies && (
                              <>
                                <RatingStars
                                  rating={Number(offer.companies.rating_avg)}
                                  count={offer.companies.rating_count}
                                />
                                <VerificationBadge
                                  level={offer.companies.verification_level as VerificationLevel}
                                />
                              </>
                            )}
                          </div>
                        </div>
                      </Link>
                      <div className="text-right">
                        <div className="text-2xl font-bold">
                          {formatMoney(Number(offer.price), offer.currency)}
                        </div>
                        {offer.estimated_days && (
                          <div className="text-xs text-muted-foreground">
                            ~{offer.estimated_days} days
                          </div>
                        )}
                      </div>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">{offer.description}</p>
                    <div className="mt-4 flex items-center justify-between">
                      <Badge variant="outline" className="capitalize">{offer.status}</Badge>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          onClick={() => message.mutate(offer.company_id)}
                          disabled={message.isPending}
                        >
                          <MessagesSquare className="mr-1.5 h-4 w-4" />
                          Message
                        </Button>
                        {offer.status === "submitted" && rfq.status === "published" && (
                          <Button
                            onClick={() => accept.mutate(offer.id)}
                            disabled={accept.isPending}
                          >
                            <CheckCircle2 className="mr-1.5 h-4 w-4" />
                            Accept offer
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                No quotes yet. Matching companies have been notified — quotes
                usually arrive within a few days.
              </p>
            )}
          </div>
        )}

        {/* Quote form — companies */}
        {canQuote && (
          <Card className="mt-8">
            <CardHeader>
              <CardTitle>Submit your quote as {myCompany?.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="price">Price ({rfq.currency}) *</Label>
                  <Input
                    id="price"
                    type="number"
                    min="1"
                    value={offerPrice}
                    onChange={(e) => setOfferPrice(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="days">Estimated days</Label>
                  <Input
                    id="days"
                    type="number"
                    min="1"
                    value={offerDays}
                    onChange={(e) => setOfferDays(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="offer-description">What is included? *</Label>
                <Textarea
                  id="offer-description"
                  rows={4}
                  placeholder="Scope, materials, terms, guarantees…"
                  value={offerDescription}
                  onChange={(e) => setOfferDescription(e.target.value)}
                />
              </div>
              <Button
                disabled={!offerPrice || offerDescription.trim().length < 10 || sendOffer.isPending}
                onClick={() => sendOffer.mutate()}
              >
                <Send className="mr-1.5 h-4 w-4" />
                {sendOffer.isPending ? "Sending…" : "Send quote"}
              </Button>
            </CardContent>
          </Card>
        )}

        {myCompany && !isOwner && (
          <div className="mt-4 flex justify-end">
            <Button
              variant="outline"
              onClick={() => message.mutate(myCompany.id)}
              disabled={message.isPending}
            >
              <MessagesSquare className="mr-1.5 h-4 w-4" />
              Message the customer
            </Button>
          </div>
        )}

        {myOffer && !isOwner && (
          <div className="card-elevated mt-8 p-5">
            <h2 className="font-semibold">Your quote</h2>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xl font-bold">
                {formatMoney(Number(myOffer.price), myOffer.currency)}
              </span>
              <Badge variant="outline" className="capitalize">{myOffer.status}</Badge>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{myOffer.description}</p>
          </div>
        )}
      </div>
    </SiteLayout>
  );
}
