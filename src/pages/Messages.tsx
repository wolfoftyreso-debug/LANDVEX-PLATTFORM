import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import EmptyState from "@/components/marketplace/EmptyState";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { getMyCompany } from "@/modules/companies/api";
import {
  listMessages,
  listMyConversations,
  sendMessage,
  type Conversation,
} from "@/modules/messaging/api";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import { MessagesSquare, Send } from "lucide-react";

function conversationTitle(conversation: Conversation, isCustomerSide: boolean) {
  const base = isCustomerSide
    ? conversation.companies?.name ?? "Company"
    : "Customer";
  return conversation.rfqs?.title ? `${base} · ${conversation.rfqs.title}` : base;
}

export default function Messages() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, loading } = useAuth();
  const [params, setParams] = useSearchParams();
  const activeId = params.get("conversation");
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: myCompany } = useQuery({
    queryKey: ["my-company"],
    queryFn: getMyCompany,
    enabled: !!user,
  });

  const { data: conversations } = useQuery({
    queryKey: ["conversations", myCompany?.id],
    queryFn: () => listMyConversations(myCompany?.id),
    enabled: !!user,
  });

  const active = conversations?.find((c) => c.id === activeId) ?? null;

  const { data: messages } = useQuery({
    queryKey: ["messages", activeId],
    queryFn: () => listMessages(activeId!),
    enabled: !!activeId,
    refetchInterval: 5000,
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages?.length]);

  const send = useMutation({
    mutationFn: () => sendMessage(activeId!, draft.trim()),
    onSuccess: () => {
      setDraft("");
      queryClient.invalidateQueries({ queryKey: ["messages", activeId] });
    },
  });

  if (!loading && !user) {
    navigate("/auth?next=/messages");
    return null;
  }

  return (
    <SiteLayout>
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold">Messages</h1>
        <div className="card-elevated mt-6 grid min-h-[60vh] overflow-hidden md:grid-cols-[300px_1fr]">
          {/* Conversation list */}
          <div className="border-r">
            {conversations && conversations.length > 0 ? (
              conversations.map((conversation) => {
                const isCustomerSide = conversation.customer_id === user?.id;
                return (
                  <button
                    key={conversation.id}
                    type="button"
                    onClick={() => setParams({ conversation: conversation.id })}
                    className={cn(
                      "flex w-full items-center gap-3 border-b px-4 py-3 text-left transition-colors hover:bg-muted/60",
                      conversation.id === activeId && "bg-muted",
                    )}
                  >
                    <Avatar className="h-9 w-9 rounded-lg">
                      <AvatarImage src={conversation.companies?.logo_url ?? undefined} />
                      <AvatarFallback className="rounded-lg bg-primary/10 text-xs font-bold text-primary">
                        {(conversation.companies?.name ?? "C").slice(0, 2).toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">
                        {conversationTitle(conversation, isCustomerSide)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {format(new Date(conversation.created_at), "d MMM yyyy")}
                      </div>
                    </div>
                  </button>
                );
              })
            ) : (
              <div className="p-6 text-sm text-muted-foreground">
                No conversations yet. Start one from a request or order.
              </div>
            )}
          </div>

          {/* Thread */}
          <div className="flex flex-col">
            {active ? (
              <>
                <div className="border-b px-4 py-3 font-semibold">
                  {conversationTitle(active, active.customer_id === user?.id)}
                </div>
                <div className="flex-1 space-y-3 overflow-y-auto p-4">
                  {messages?.map((message) => {
                    const mine = message.sender_id === user?.id;
                    return (
                      <div
                        key={message.id}
                        className={cn("flex", mine ? "justify-end" : "justify-start")}
                      >
                        <div
                          className={cn(
                            "max-w-[75%] rounded-2xl px-4 py-2 text-sm",
                            mine
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted",
                          )}
                        >
                          <p className="whitespace-pre-line">{message.body}</p>
                          <div
                            className={cn(
                              "mt-1 text-[10px]",
                              mine ? "text-primary-foreground/70" : "text-muted-foreground",
                            )}
                          >
                            {format(new Date(message.created_at), "d MMM HH:mm")}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={bottomRef} />
                </div>
                <form
                  className="flex gap-2 border-t p-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (draft.trim()) send.mutate();
                  }}
                >
                  <Input
                    placeholder="Write a message…"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                  <Button type="submit" disabled={!draft.trim() || send.isPending}>
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
              </>
            ) : (
              <div className="flex flex-1 items-center justify-center p-8">
                <EmptyState
                  icon={MessagesSquare}
                  title="Select a conversation"
                  description="Choose a conversation from the list, or start one from a request or order page."
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </SiteLayout>
  );
}
