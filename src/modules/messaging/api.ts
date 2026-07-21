import { db, supabase } from "@/modules/core/db";

export interface Conversation {
  id: string;
  rfq_id: string | null;
  order_id: string | null;
  customer_id: string;
  company_id: string;
  created_at: string;
  companies?: { id: string; name: string; slug: string; logo_url: string | null };
  rfqs?: { id: string; title: string } | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string;
  body: string;
  created_at: string;
  read_at: string | null;
}

const CONVERSATION_SELECT =
  "*, companies(id, name, slug, logo_url), rfqs(id, title)";

/** Reuse an existing conversation for (rfq, company) or start a new one. */
export async function getOrCreateConversation(params: {
  companyId: string;
  customerId: string;
  rfqId?: string | null;
  orderId?: string | null;
}): Promise<Conversation> {
  let query = db
    .from("conversations")
    .select(CONVERSATION_SELECT)
    .eq("company_id", params.companyId)
    .eq("customer_id", params.customerId);
  if (params.rfqId) query = query.eq("rfq_id", params.rfqId);

  const { data: existing, error: findError } = await query.limit(1);
  if (findError) throw findError;
  if (existing && existing.length > 0) return existing[0] as Conversation;

  const { data, error } = await db
    .from("conversations")
    .insert({
      company_id: params.companyId,
      customer_id: params.customerId,
      rfq_id: params.rfqId ?? null,
      order_id: params.orderId ?? null,
    })
    .select(CONVERSATION_SELECT)
    .single();
  if (error) throw error;
  return data as Conversation;
}

export async function listMyConversations(
  myCompanyId?: string | null,
): Promise<Conversation[]> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) return [];

  let query = db
    .from("conversations")
    .select(CONVERSATION_SELECT)
    .order("created_at", { ascending: false });

  if (myCompanyId) {
    query = query.or(`customer_id.eq.${userId},company_id.eq.${myCompanyId}`);
  } else {
    query = query.eq("customer_id", userId);
  }

  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Conversation[];
}

export async function listMessages(conversationId: string): Promise<Message[]> {
  const { data, error } = await db
    .from("messages")
    .select("*")
    .eq("conversation_id", conversationId)
    .order("created_at", { ascending: true });
  if (error) throw error;
  return (data ?? []) as Message[];
}

export async function sendMessage(
  conversationId: string,
  body: string,
): Promise<Message> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) throw new Error("You must be signed in to send messages");

  const { data, error } = await db
    .from("messages")
    .insert({ conversation_id: conversationId, sender_id: userId, body })
    .select()
    .single();
  if (error) throw error;
  return data as Message;
}
