-- ============================================================================
-- BALTIC BRIDGE — Notifications engine, verification back office, messaging
-- Domain events fan out to in-app notifications via triggers.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Helper: notify every member (incl. owner) of a company
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.notify_company(
  _company_id UUID,
  _type TEXT,
  _title TEXT,
  _body TEXT,
  _link TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.notifications (user_id, type, title, body, link)
  SELECT DISTINCT u.user_id, _type, _title, _body, _link
  FROM (
    SELECT owner_id AS user_id FROM public.companies WHERE id = _company_id
    UNION
    SELECT user_id FROM public.company_members WHERE company_id = _company_id
  ) u;
END;
$$;

-- ---------------------------------------------------------------------------
-- Event: RfqPublished -> notify companies whose services match the category
-- and whose country coverage includes the RFQ country
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.on_rfq_published()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.status = 'published' AND NEW.category_id IS NOT NULL THEN
    INSERT INTO public.notifications (user_id, type, title, body, link)
    SELECT DISTINCT members.user_id,
           'rfq.matched',
           'New request matching your services',
           NEW.title,
           '/rfq/' || NEW.id
    FROM public.company_services cs
    JOIN public.companies c ON c.id = cs.company_id
    CROSS JOIN LATERAL (
      SELECT c.owner_id AS user_id
      UNION
      SELECT m.user_id FROM public.company_members m WHERE m.company_id = c.id
    ) members
    WHERE cs.category_id = NEW.category_id
      AND (c.country = NEW.country OR NEW.country = ANY (c.countries_served))
      AND members.user_id <> NEW.customer_id;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_rfq_published
  AFTER INSERT ON public.rfqs
  FOR EACH ROW EXECUTE FUNCTION public.on_rfq_published();

-- ---------------------------------------------------------------------------
-- Event: OfferSubmitted -> notify the RFQ owner
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.on_offer_submitted()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_rfq RECORD;
  v_company_name TEXT;
BEGIN
  SELECT * INTO v_rfq FROM public.rfqs WHERE id = NEW.rfq_id;
  SELECT name INTO v_company_name FROM public.companies WHERE id = NEW.company_id;

  INSERT INTO public.notifications (user_id, type, title, body, link)
  VALUES (
    v_rfq.customer_id,
    'offer.submitted',
    'New quote received',
    v_company_name || ' sent a quote on "' || v_rfq.title || '"',
    '/rfq/' || NEW.rfq_id
  );
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_offer_submitted
  AFTER INSERT ON public.offers
  FOR EACH ROW EXECUTE FUNCTION public.on_offer_submitted();

-- ---------------------------------------------------------------------------
-- Event: OrderCreated -> notify the company; order status changes -> notify
-- the counterpart
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.on_order_created_notify()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_title TEXT;
BEGIN
  SELECT title INTO v_title FROM public.rfqs WHERE id = NEW.rfq_id;
  PERFORM public.notify_company(
    NEW.company_id,
    'order.created',
    'Your quote was accepted 🎉',
    'Order created for "' || COALESCE(v_title, 'your quote') || '"',
    '/order/' || NEW.id
  );
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_order_created_notify
  AFTER INSERT ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.on_order_created_notify();

CREATE OR REPLACE FUNCTION public.on_order_status_notify()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_title TEXT;
  v_label TEXT;
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    SELECT title INTO v_title FROM public.rfqs WHERE id = NEW.rfq_id;
    v_label := replace(NEW.status::text, '_', ' ');

    -- Notify the customer for company-driven transitions, and the company
    -- for customer-driven ones; keep it simple and notify both sides.
    INSERT INTO public.notifications (user_id, type, title, body, link)
    VALUES (
      NEW.customer_id,
      'order.status',
      'Order update: ' || v_label,
      COALESCE(v_title, 'Your order') || ' is now ' || v_label,
      '/order/' || NEW.id
    );
    PERFORM public.notify_company(
      NEW.company_id,
      'order.status',
      'Order update: ' || v_label,
      COALESCE(v_title, 'Order') || ' is now ' || v_label,
      '/order/' || NEW.id
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_order_status_notify
  AFTER UPDATE ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.on_order_status_notify();

-- ---------------------------------------------------------------------------
-- Event: MessageSent -> notify the other participant(s)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.on_message_sent()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_conv RECORD;
BEGIN
  SELECT * INTO v_conv FROM public.conversations WHERE id = NEW.conversation_id;

  IF NEW.sender_id = v_conv.customer_id THEN
    PERFORM public.notify_company(
      v_conv.company_id,
      'message.new',
      'New message',
      left(NEW.body, 120),
      '/messages?conversation=' || NEW.conversation_id
    );
  ELSE
    INSERT INTO public.notifications (user_id, type, title, body, link)
    VALUES (
      v_conv.customer_id,
      'message.new',
      'New message',
      left(NEW.body, 120),
      '/messages?conversation=' || NEW.conversation_id
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_message_sent
  AFTER INSERT ON public.messages
  FOR EACH ROW EXECUTE FUNCTION public.on_message_sent();

-- ---------------------------------------------------------------------------
-- VERIFICATION BACK OFFICE
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid() AND role = 'admin'
  );
$$;

-- Admins see and manage all verification requests
CREATE POLICY "Admins view all verification requests" ON public.verification_requests
  FOR SELECT USING (public.is_admin());
CREATE POLICY "Admins update verification requests" ON public.verification_requests
  FOR UPDATE USING (public.is_admin());

-- Transactional review: approve/reject a request and update the company
CREATE OR REPLACE FUNCTION public.review_verification(
  _request_id UUID,
  _approve BOOLEAN,
  _notes TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_req RECORD;
BEGIN
  IF NOT public.is_admin() THEN
    RAISE EXCEPTION 'Only administrators can review verification requests';
  END IF;

  SELECT * INTO v_req FROM public.verification_requests
  WHERE id = _request_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Verification request not found'; END IF;
  IF v_req.status <> 'pending' THEN RAISE EXCEPTION 'Request already reviewed'; END IF;

  UPDATE public.verification_requests
  SET status = CASE WHEN _approve THEN 'approved'::public.verification_request_status
                    ELSE 'rejected'::public.verification_request_status END,
      notes = COALESCE(_notes, notes),
      reviewed_at = now()
  WHERE id = _request_id;

  IF _approve THEN
    UPDATE public.companies
    SET verification_level = v_req.requested_level,
        identity_verified = true,
        vat_verified = CASE WHEN vat_number IS NOT NULL THEN true ELSE vat_verified END
    WHERE id = v_req.company_id;

    PERFORM public.notify_company(
      v_req.company_id,
      'verification.approved',
      'Verification approved',
      'Your company is now ' || v_req.requested_level::text || ' verified.',
      '/dashboard'
    );
  ELSE
    PERFORM public.notify_company(
      v_req.company_id,
      'verification.rejected',
      'Verification request rejected',
      COALESCE(_notes, 'Contact support for details.'),
      '/dashboard'
    );
  END IF;

  INSERT INTO public.audit_log (actor_id, action, entity_type, entity_id, data)
  VALUES (
    auth.uid(),
    CASE WHEN _approve THEN 'verification.approved' ELSE 'verification.rejected' END,
    'verification_request',
    _request_id,
    jsonb_build_object('company_id', v_req.company_id, 'level', v_req.requested_level)
  );
END;
$$;

-- Admins can read companies join info needed in back office (already public).
-- Allow admins to list pending requests with company names via a view.
CREATE OR REPLACE VIEW public.verification_queue
WITH (security_invoker = on) AS
SELECT vr.*, c.name AS company_name, c.slug AS company_slug,
       c.country AS company_country, c.vat_number, c.org_number
FROM public.verification_requests vr
JOIN public.companies c ON c.id = vr.company_id;

-- ---------------------------------------------------------------------------
-- Realtime for messages and notifications
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.messages;
    ALTER PUBLICATION supabase_realtime ADD TABLE public.notifications;
  END IF;
EXCEPTION WHEN duplicate_object THEN
  NULL;
END;
$$;
