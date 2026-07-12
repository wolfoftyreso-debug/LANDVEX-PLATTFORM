import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";
import { verifyWebhook, type StripeEnv } from "../_shared/stripe.ts";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

/** Find existing auth user by email, or create one and send magic-link invite. */
async function ensureUser(email: string, companyName?: string): Promise<string | null> {
  if (!email) return null;
  try {
    // Search by email (paginated). For low volumes this is fine.
    const { data: list } = await supabase.auth.admin.listUsers({ page: 1, perPage: 200 });
    const existing = list?.users?.find((u) => u.email?.toLowerCase() === email.toLowerCase());
    if (existing) return existing.id;

    // Create + invite so kunden får ett välkomstmejl med länk att sätta lösenord.
    const siteUrl = Deno.env.get("SUPABASE_URL")?.replace(".supabase.co", ".lovable.app") ?? undefined;
    const { data: invited, error: inviteErr } = await supabase.auth.admin.inviteUserByEmail(email, {
      data: { company_name: companyName ?? null },
      redirectTo: siteUrl ? `${siteUrl}/account` : undefined,
    });
    if (inviteErr) {
      console.error("inviteUserByEmail failed:", inviteErr);
      return null;
    }
    return invited?.user?.id ?? null;
  } catch (e) {
    console.error("ensureUser error:", e);
    return null;
  }
}

async function upsertSubscription(sub: any, env: StripeEnv) {
  const item = sub.items?.data?.[0];
  const priceId = item?.price?.lookup_key || item?.price?.id;
  const periodStart = item?.current_period_start ?? sub.current_period_start;
  const periodEnd = item?.current_period_end ?? sub.current_period_end;

  const customerEmail: string =
    sub.metadata?.customer_email ||
    sub.customer_email ||
    (typeof sub.customer === "object" ? sub.customer?.email : null) ||
    "";
  const companyName = sub.metadata?.company ?? null;
  const kgPerWeek = sub.metadata?.kg_per_week ? Number(sub.metadata.kg_per_week) : null;
  const unitAmount = item?.price?.unit_amount ?? 0;
  const quantity = item?.quantity ?? 1;
  const monthlyAmount = (unitAmount * quantity) / 100;

  // Ensure a Lovable Cloud user exists for this email, unless we can already
  // link via customer metadata.userId (future-proof).
  let userId: string | null = sub.metadata?.userId ?? null;
  if (!userId && customerEmail) {
    userId = await ensureUser(customerEmail, companyName ?? undefined);
  }

  await supabase.from("subscriptions").upsert(
    {
      user_id: userId,
      customer_email: customerEmail,
      company_name: companyName,
      stripe_subscription_id: sub.id,
      stripe_customer_id: typeof sub.customer === "string" ? sub.customer : sub.customer?.id,
      price_id: priceId,
      kg_per_week: kgPerWeek,
      monthly_amount: monthlyAmount || null,
      status: sub.status,
      collection_method: sub.collection_method ?? null,
      current_period_start: periodStart ? new Date(periodStart * 1000).toISOString() : null,
      current_period_end: periodEnd ? new Date(periodEnd * 1000).toISOString() : null,
      cancel_at_period_end: !!sub.cancel_at_period_end,
      environment: env,
      updated_at: new Date().toISOString(),
    },
    { onConflict: "stripe_subscription_id" },
  );
}

async function markCanceled(sub: any, env: StripeEnv) {
  const periodEnd = sub.items?.data?.[0]?.current_period_end ?? sub.current_period_end;
  await supabase
    .from("subscriptions")
    .update({
      status: "canceled",
      cancel_at_period_end: !!sub.cancel_at_period_end,
      current_period_end: periodEnd ? new Date(periodEnd * 1000).toISOString() : null,
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", sub.id)
    .eq("environment", env);
}

async function handleCheckoutCompleted(session: any, env: StripeEnv) {
  // For subscription checkouts, subscription events kommer separat — men
  // vi ser till att koppla user_id om vi har e-post redan här.
  const email = session.customer_details?.email || session.customer_email;
  if (email) {
    await ensureUser(email, session.metadata?.company);
  }

  // Markera ordern som betald genom att matcha stripe_session_id i items[0].
  const paid = session.payment_status === "paid" || session.status === "complete";
  if (paid && session.id) {
    const { data: rows, error: selErr } = await supabase
      .from("orders")
      .select("id, items, status")
      .contains("items", [{ stripe_session_id: session.id }]);
    if (selErr) console.error("orders select failed:", selErr);
    if (rows?.length) {
      for (const row of rows) {
        if (row.status === "paid") continue;
        await supabase
          .from("orders")
          .update({ status: "paid", updated_at: new Date().toISOString() })
          .eq("id", row.id);
      }
    }
  }
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });

  const rawEnv = new URL(req.url).searchParams.get("env");
  if (rawEnv !== "sandbox" && rawEnv !== "live") {
    return new Response(JSON.stringify({ received: true, ignored: "invalid env" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  const env: StripeEnv = rawEnv;

  try {
    const event = await verifyWebhook(req, env);
    console.log(`[payments-webhook:${env}] ${event.type}`);

    switch (event.type) {
      case "customer.subscription.created":
      case "customer.subscription.updated":
        await upsertSubscription(event.data.object, env);
        break;
      case "customer.subscription.deleted":
        await markCanceled(event.data.object, env);
        break;
      case "checkout.session.completed":
        await handleCheckoutCompleted(event.data.object, env);
        break;
      default:
        // ignore
        break;
    }

    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("Webhook error:", e);
    return new Response("Webhook error", { status: 400 });
  }
});
