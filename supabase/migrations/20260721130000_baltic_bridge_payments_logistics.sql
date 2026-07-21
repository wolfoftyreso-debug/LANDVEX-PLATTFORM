-- ============================================================================
-- BALTIC BRIDGE — Payments module (escrow-style) + Logistics module
-- Payments: funds are secured when the order starts and released to the
-- company when the customer approves completion.
-- Logistics: independent module — it references orders by plain UUID only
-- (reference_type/reference_id), never by foreign key, so it can serve any
-- vertical or run standalone.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
CREATE TYPE public.payment_status AS ENUM
  ('pending', 'held_in_escrow', 'released', 'refunded', 'cancelled');

CREATE TYPE public.shipment_status AS ENUM
  ('requested', 'booked', 'picked_up', 'in_transit', 'delivered', 'cancelled');

-- ---------------------------------------------------------------------------
-- PAYMENTS
-- ---------------------------------------------------------------------------
CREATE TABLE public.order_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL UNIQUE REFERENCES public.marketplace_orders(id) ON DELETE CASCADE,
  amount NUMERIC(12,2) NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  status public.payment_status NOT NULL DEFAULT 'pending',
  -- Provider abstraction: 'manual' today, 'stripe' etc. when a PSP is wired in
  provider TEXT NOT NULL DEFAULT 'manual',
  provider_reference TEXT,
  paid_at TIMESTAMPTZ,
  released_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER order_payments_updated_at
  BEFORE UPDATE ON public.order_payments
  FOR EACH ROW EXECUTE FUNCTION public.bb_set_updated_at();

ALTER TABLE public.order_payments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Order parties view payments" ON public.order_payments
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.marketplace_orders o
      WHERE o.id = order_id
        AND (o.customer_id = auth.uid() OR public.is_company_member(o.company_id))
    )
  );
-- All writes go through SECURITY DEFINER functions below.

-- Every new order gets a payment record
CREATE OR REPLACE FUNCTION public.on_order_created_payment()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.order_payments (order_id, amount, currency)
  VALUES (NEW.id, NEW.amount, NEW.currency);
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_order_created_payment
  AFTER INSERT ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.on_order_created_payment();

-- Customer secures funds in escrow
CREATE OR REPLACE FUNCTION public.pay_order_escrow(_order_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_order RECORD;
  v_payment RECORD;
BEGIN
  SELECT * INTO v_order FROM public.marketplace_orders WHERE id = _order_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'Order not found'; END IF;
  IF v_order.customer_id <> auth.uid() THEN
    RAISE EXCEPTION 'Only the customer can pay for this order';
  END IF;

  SELECT * INTO v_payment FROM public.order_payments
  WHERE order_id = _order_id FOR UPDATE;
  IF v_payment.status <> 'pending' THEN
    RAISE EXCEPTION 'Payment is not pending';
  END IF;

  UPDATE public.order_payments
  SET status = 'held_in_escrow', paid_at = now()
  WHERE order_id = _order_id;

  PERFORM public.notify_company(
    v_order.company_id,
    'payment.escrow',
    'Payment secured in escrow',
    'The customer has secured the full order amount. It is released when the order is completed.',
    '/order/' || _order_id
  );

  INSERT INTO public.audit_log (actor_id, action, entity_type, entity_id, data)
  VALUES (auth.uid(), 'payment.escrowed', 'order_payment', v_payment.id,
          jsonb_build_object('order_id', _order_id, 'amount', v_payment.amount));
END;
$$;

-- Escrow is released automatically when the customer approves completion
CREATE OR REPLACE FUNCTION public.on_order_completed_release_escrow()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.status = 'completed' AND OLD.status IS DISTINCT FROM 'completed' THEN
    UPDATE public.order_payments
    SET status = 'released', released_at = now()
    WHERE order_id = NEW.id AND status = 'held_in_escrow';

    IF FOUND THEN
      PERFORM public.notify_company(
        NEW.company_id,
        'payment.released',
        'Payment released 💶',
        'The escrowed amount for the completed order has been released to you.',
        '/order/' || NEW.id
      );
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_order_completed_release_escrow
  AFTER UPDATE ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.on_order_completed_release_escrow();

-- Admin refunds (dispute resolution)
CREATE OR REPLACE FUNCTION public.refund_order_payment(_order_id UUID, _reason TEXT DEFAULT NULL)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_order RECORD;
BEGIN
  IF NOT public.is_admin() THEN
    RAISE EXCEPTION 'Only administrators can refund payments';
  END IF;

  SELECT * INTO v_order FROM public.marketplace_orders WHERE id = _order_id;

  UPDATE public.order_payments
  SET status = 'refunded'
  WHERE order_id = _order_id AND status = 'held_in_escrow';
  IF NOT FOUND THEN RAISE EXCEPTION 'No escrowed payment to refund'; END IF;

  INSERT INTO public.notifications (user_id, type, title, body, link)
  VALUES (v_order.customer_id, 'payment.refunded', 'Payment refunded',
          COALESCE(_reason, 'Your escrowed payment has been refunded.'),
          '/order/' || _order_id);

  INSERT INTO public.audit_log (actor_id, action, entity_type, entity_id, data)
  VALUES (auth.uid(), 'payment.refunded', 'marketplace_order', _order_id,
          jsonb_build_object('reason', _reason));
END;
$$;

-- ---------------------------------------------------------------------------
-- LOGISTICS (independent module)
-- ---------------------------------------------------------------------------
CREATE TABLE public.shipments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Loose coupling: no FK into marketplace tables
  reference_type TEXT NOT NULL DEFAULT 'marketplace_order',
  reference_id UUID,
  requester_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  counterpart_company_id UUID,
  pickup_address TEXT NOT NULL,
  pickup_country TEXT NOT NULL,
  delivery_address TEXT NOT NULL,
  delivery_country TEXT NOT NULL,
  insured BOOLEAN NOT NULL DEFAULT false,
  provider TEXT,
  tracking_code TEXT,
  price NUMERIC(12,2),
  currency TEXT NOT NULL DEFAULT 'EUR',
  estimated_delivery DATE,
  status public.shipment_status NOT NULL DEFAULT 'requested',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_shipments_reference ON public.shipments(reference_type, reference_id);

CREATE TRIGGER shipments_updated_at
  BEFORE UPDATE ON public.shipments
  FOR EACH ROW EXECUTE FUNCTION public.bb_set_updated_at();

ALTER TABLE public.shipments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Shipment parties view shipments" ON public.shipments
  FOR SELECT USING (
    requester_id = auth.uid()
    OR (counterpart_company_id IS NOT NULL
        AND public.is_company_member(counterpart_company_id))
  );
CREATE POLICY "Users request shipments" ON public.shipments
  FOR INSERT WITH CHECK (requester_id = auth.uid());
CREATE POLICY "Shipment parties update shipments" ON public.shipments
  FOR UPDATE USING (
    requester_id = auth.uid()
    OR (counterpart_company_id IS NOT NULL
        AND public.is_company_member(counterpart_company_id))
  );

-- Notify both sides on status changes
CREATE OR REPLACE FUNCTION public.on_shipment_status_notify()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_label TEXT;
  v_link TEXT;
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    v_label := replace(NEW.status::text, '_', ' ');
    v_link := CASE WHEN NEW.reference_type = 'marketplace_order' AND NEW.reference_id IS NOT NULL
                   THEN '/order/' || NEW.reference_id ELSE '/dashboard' END;

    INSERT INTO public.notifications (user_id, type, title, body, link)
    VALUES (NEW.requester_id, 'shipment.status',
            'Transport update: ' || v_label,
            COALESCE('Tracking: ' || NEW.tracking_code, 'Your transport is now ' || v_label),
            v_link);

    IF NEW.counterpart_company_id IS NOT NULL THEN
      PERFORM public.notify_company(
        NEW.counterpart_company_id,
        'shipment.status',
        'Transport update: ' || v_label,
        'The transport for your order is now ' || v_label,
        v_link
      );
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_shipment_status_notify
  AFTER UPDATE ON public.shipments
  FOR EACH ROW EXECUTE FUNCTION public.on_shipment_status_notify();
