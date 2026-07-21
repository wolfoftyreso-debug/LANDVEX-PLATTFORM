-- ============================================================================
-- BALTIC BRIDGE — Marketplace core schema
-- Modules: Companies, Verification, Trust Engine, RFQ, Offers, Orders,
--          Reviews, Messaging, Notifications, Media, Audit
-- The marketplace engine is generic: verticals + categories are data, and
-- vertical-specific RFQ fields live in schema-versioned JSONB metadata.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
CREATE TYPE public.verification_level AS ENUM
  ('unverified', 'bronze', 'silver', 'gold', 'platinum');

CREATE TYPE public.availability_status AS ENUM
  ('available', 'busy', 'unavailable');

CREATE TYPE public.rfq_status AS ENUM
  ('draft', 'published', 'accepted', 'expired', 'withdrawn');

CREATE TYPE public.offer_status AS ENUM
  ('submitted', 'withdrawn', 'accepted', 'rejected');

CREATE TYPE public.mp_order_status AS ENUM
  ('created', 'in_progress', 'delivered', 'completed', 'disputed', 'cancelled');

CREATE TYPE public.verification_request_status AS ENUM
  ('pending', 'approved', 'rejected');

-- ---------------------------------------------------------------------------
-- Helper: updated_at maintenance
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.bb_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Verticals & categories (multi-tenant marketplace engine)
-- ---------------------------------------------------------------------------
CREATE TABLE public.verticals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT,
  icon TEXT,
  active BOOLEAN NOT NULL DEFAULT true,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vertical_id UUID NOT NULL REFERENCES public.verticals(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  parent_id UUID REFERENCES public.categories(id) ON DELETE SET NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (vertical_id, slug)
);

-- ---------------------------------------------------------------------------
-- Companies
-- ---------------------------------------------------------------------------
CREATE TABLE public.companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT,
  logo_url TEXT,
  cover_url TEXT,
  country TEXT NOT NULL,           -- ISO 3166-1 alpha-2
  region TEXT,
  city TEXT,
  address TEXT,
  countries_served TEXT[] NOT NULL DEFAULT '{}',
  languages TEXT[] NOT NULL DEFAULT '{}',
  contact_email TEXT,
  contact_phone TEXT,
  website TEXT,
  vat_number TEXT,
  org_number TEXT,
  year_founded INT,
  employee_count INT,
  certifications TEXT[] NOT NULL DEFAULT '{}',
  licenses TEXT[] NOT NULL DEFAULT '{}',
  insurance_info TEXT,
  availability public.availability_status NOT NULL DEFAULT 'available',
  -- Verification module projections
  verification_level public.verification_level NOT NULL DEFAULT 'unverified',
  identity_verified BOOLEAN NOT NULL DEFAULT false,
  vat_verified BOOLEAN NOT NULL DEFAULT false,
  -- Trust Engine / stats projections (denormalized read model)
  trust_score NUMERIC(5,2) NOT NULL DEFAULT 0,
  rating_avg NUMERIC(3,2) NOT NULL DEFAULT 0,
  rating_count INT NOT NULL DEFAULT 0,
  completed_projects INT NOT NULL DEFAULT 0,
  repeat_customers INT NOT NULL DEFAULT 0,
  response_rate NUMERIC(5,2),
  avg_response_hours NUMERIC(8,2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_companies_country ON public.companies(country);
CREATE INDEX idx_companies_trust ON public.companies(trust_score DESC);

CREATE TRIGGER companies_updated_at
  BEFORE UPDATE ON public.companies
  FOR EACH ROW EXECUTE FUNCTION public.bb_set_updated_at();

CREATE TABLE public.company_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (company_id, user_id)
);

CREATE TABLE public.company_services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  category_id UUID NOT NULL REFERENCES public.categories(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (company_id, category_id)
);

CREATE TABLE public.portfolio_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  image_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Membership helper (SECURITY DEFINER avoids recursive RLS)
CREATE OR REPLACE FUNCTION public.is_company_member(_company_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.companies c
    WHERE c.id = _company_id AND c.owner_id = auth.uid()
  ) OR EXISTS (
    SELECT 1 FROM public.company_members m
    WHERE m.company_id = _company_id AND m.user_id = auth.uid()
  );
$$;

-- ---------------------------------------------------------------------------
-- RFQ (Request For Quote)
-- ---------------------------------------------------------------------------
CREATE TABLE public.rfqs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  vertical_id UUID NOT NULL REFERENCES public.verticals(id),
  category_id UUID REFERENCES public.categories(id),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  country TEXT NOT NULL,
  region TEXT,
  city TEXT,
  address TEXT,
  budget_min NUMERIC(12,2),
  budget_max NUMERIC(12,2),
  currency TEXT NOT NULL DEFAULT 'EUR',
  deadline DATE,
  preferred_language TEXT,
  -- Vertical-specific fields (schema-versioned JSONB, validated in app layer)
  metadata JSONB NOT NULL DEFAULT '{}',
  metadata_schema_version INT NOT NULL DEFAULT 1,
  status public.rfq_status NOT NULL DEFAULT 'published',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rfqs_status ON public.rfqs(status);
CREATE INDEX idx_rfqs_vertical ON public.rfqs(vertical_id);
CREATE INDEX idx_rfqs_customer ON public.rfqs(customer_id);

CREATE TRIGGER rfqs_updated_at
  BEFORE UPDATE ON public.rfqs
  FOR EACH ROW EXECUTE FUNCTION public.bb_set_updated_at();

CREATE TABLE public.rfq_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rfq_id UUID NOT NULL REFERENCES public.rfqs(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Offers
-- ---------------------------------------------------------------------------
CREATE TABLE public.offers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rfq_id UUID NOT NULL REFERENCES public.rfqs(id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  price NUMERIC(12,2) NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  description TEXT NOT NULL,
  valid_until DATE,
  estimated_start DATE,
  estimated_days INT,
  status public.offer_status NOT NULL DEFAULT 'submitted',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rfq_id, company_id)
);

CREATE INDEX idx_offers_rfq ON public.offers(rfq_id);
CREATE INDEX idx_offers_company ON public.offers(company_id);

CREATE TRIGGER offers_updated_at
  BEFORE UPDATE ON public.offers
  FOR EACH ROW EXECUTE FUNCTION public.bb_set_updated_at();

-- ---------------------------------------------------------------------------
-- Orders (named marketplace_orders: legacy `orders` belongs to retired shop)
-- ---------------------------------------------------------------------------
CREATE TABLE public.marketplace_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rfq_id UUID NOT NULL REFERENCES public.rfqs(id),
  offer_id UUID NOT NULL UNIQUE REFERENCES public.offers(id),
  company_id UUID NOT NULL REFERENCES public.companies(id),
  customer_id UUID NOT NULL REFERENCES auth.users(id),
  amount NUMERIC(12,2) NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  status public.mp_order_status NOT NULL DEFAULT 'created',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX idx_mp_orders_company ON public.marketplace_orders(company_id);
CREATE INDEX idx_mp_orders_customer ON public.marketplace_orders(customer_id);

CREATE TRIGGER marketplace_orders_updated_at
  BEFORE UPDATE ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.bb_set_updated_at();

-- ---------------------------------------------------------------------------
-- Reviews (verified customers only, one per completed order)
-- ---------------------------------------------------------------------------
CREATE TABLE public.reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL UNIQUE REFERENCES public.marketplace_orders(id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  customer_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  rating_overall INT NOT NULL CHECK (rating_overall BETWEEN 1 AND 5),
  rating_communication INT CHECK (rating_communication BETWEEN 1 AND 5),
  rating_quality INT CHECK (rating_quality BETWEEN 1 AND 5),
  rating_price INT CHECK (rating_price BETWEEN 1 AND 5),
  rating_delivery INT CHECK (rating_delivery BETWEEN 1 AND 5),
  rating_professionalism INT CHECK (rating_professionalism BETWEEN 1 AND 5),
  would_recommend BOOLEAN NOT NULL DEFAULT true,
  comment TEXT,
  project_description TEXT,
  photos TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_reviews_company ON public.reviews(company_id);

-- ---------------------------------------------------------------------------
-- Messaging
-- ---------------------------------------------------------------------------
CREATE TABLE public.conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rfq_id UUID REFERENCES public.rfqs(id) ON DELETE SET NULL,
  order_id UUID REFERENCES public.marketplace_orders(id) ON DELETE SET NULL,
  customer_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rfq_id, company_id)
);

CREATE TABLE public.messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
  sender_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  read_at TIMESTAMPTZ
);

CREATE INDEX idx_messages_conversation ON public.messages(conversation_id);

CREATE OR REPLACE FUNCTION public.is_conversation_participant(_conversation_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.conversations c
    WHERE c.id = _conversation_id
      AND (c.customer_id = auth.uid() OR public.is_company_member(c.company_id))
  );
$$;

-- ---------------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------------
CREATE TABLE public.verification_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  requested_level public.verification_level NOT NULL,
  documents JSONB NOT NULL DEFAULT '[]',
  status public.verification_request_status NOT NULL DEFAULT 'pending',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- Notifications & audit
-- ---------------------------------------------------------------------------
CREATE TABLE public.notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  link TEXT,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user ON public.notifications(user_id, read_at);

CREATE TABLE public.audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  data JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- TRUST ENGINE
-- Weighted, explainable score 0-100, recalculated on domain events.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.recalc_trust_score(_company_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  c RECORD;
  v_score NUMERIC := 0;
  v_level_points NUMERIC;
  v_age_years NUMERIC;
BEGIN
  SELECT * INTO c FROM public.companies WHERE id = _company_id;
  IF NOT FOUND THEN RETURN; END IF;

  -- Verification level: up to 25
  v_level_points := CASE c.verification_level
    WHEN 'platinum' THEN 25
    WHEN 'gold' THEN 20
    WHEN 'silver' THEN 14
    WHEN 'bronze' THEN 8
    ELSE 0 END;
  v_score := v_score + v_level_points;

  -- Verified identity + VAT: up to 10
  IF c.identity_verified THEN v_score := v_score + 5; END IF;
  IF c.vat_verified THEN v_score := v_score + 5; END IF;

  -- Company age: up to 10 (1 point per year, capped)
  IF c.year_founded IS NOT NULL THEN
    v_age_years := GREATEST(0, EXTRACT(YEAR FROM now()) - c.year_founded);
    v_score := v_score + LEAST(10, v_age_years);
  END IF;

  -- Completed projects: up to 20 (2 points each, capped)
  v_score := v_score + LEAST(20, c.completed_projects * 2);

  -- Reviews: up to 25 (average rating scaled, weighted by volume)
  IF c.rating_count > 0 THEN
    v_score := v_score
      + (c.rating_avg / 5.0) * 20
      + LEAST(5, c.rating_count * 0.5);
  END IF;

  -- Response rate: up to 10
  IF c.response_rate IS NOT NULL THEN
    v_score := v_score + (c.response_rate / 100.0) * 10;
  END IF;

  UPDATE public.companies
  SET trust_score = LEAST(100, ROUND(v_score, 2))
  WHERE id = _company_id;
END;
$$;

-- Event: ReviewPublished -> update rating projections + trust score
CREATE OR REPLACE FUNCTION public.on_review_published()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.companies c SET
    rating_avg = sub.avg_rating,
    rating_count = sub.cnt
  FROM (
    SELECT AVG(rating_overall)::NUMERIC(3,2) AS avg_rating, COUNT(*) AS cnt
    FROM public.reviews WHERE company_id = NEW.company_id
  ) sub
  WHERE c.id = NEW.company_id;

  PERFORM public.recalc_trust_score(NEW.company_id);
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_review_published
  AFTER INSERT ON public.reviews
  FOR EACH ROW EXECUTE FUNCTION public.on_review_published();

-- Event: OrderCompleted -> stamp completion time (BEFORE), then update
-- completed projects + repeat customers + trust score (AFTER)
CREATE OR REPLACE FUNCTION public.on_order_completed_stamp()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF NEW.status = 'completed' AND OLD.status IS DISTINCT FROM 'completed' THEN
    NEW.completed_at := now();
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_order_completed_stamp
  BEFORE UPDATE ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.on_order_completed_stamp();

CREATE OR REPLACE FUNCTION public.on_order_completed_stats()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.status = 'completed' AND OLD.status IS DISTINCT FROM 'completed' THEN
    UPDATE public.companies c SET
      completed_projects = sub.total_orders,
      repeat_customers = sub.repeats
    FROM (
      SELECT COALESCE(SUM(per_customer.n), 0) AS total_orders,
             COUNT(*) FILTER (WHERE per_customer.n > 1) AS repeats
      FROM (
        SELECT customer_id, COUNT(*) AS n
        FROM public.marketplace_orders
        WHERE company_id = NEW.company_id AND status = 'completed'
        GROUP BY customer_id
      ) per_customer
    ) sub
    WHERE c.id = NEW.company_id;

    PERFORM public.recalc_trust_score(NEW.company_id);
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_order_completed_stats
  AFTER UPDATE ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.on_order_completed_stats();

-- Event: VerificationLevelChanged -> trust
CREATE OR REPLACE FUNCTION public.on_company_verification_changed()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.verification_level IS DISTINCT FROM OLD.verification_level
     OR NEW.identity_verified IS DISTINCT FROM OLD.identity_verified
     OR NEW.vat_verified IS DISTINCT FROM OLD.vat_verified THEN
    PERFORM public.recalc_trust_score(NEW.id);
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_company_verification_changed
  AFTER UPDATE ON public.companies
  FOR EACH ROW EXECUTE FUNCTION public.on_company_verification_changed();

-- ---------------------------------------------------------------------------
-- Accept offer: transactional accept + order creation (application service)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.accept_offer(_offer_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_offer RECORD;
  v_rfq RECORD;
  v_order_id UUID;
BEGIN
  SELECT * INTO v_offer FROM public.offers WHERE id = _offer_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Offer not found'; END IF;
  IF v_offer.status <> 'submitted' THEN RAISE EXCEPTION 'Offer is not open'; END IF;

  SELECT * INTO v_rfq FROM public.rfqs WHERE id = v_offer.rfq_id FOR UPDATE;
  IF v_rfq.customer_id <> auth.uid() THEN
    RAISE EXCEPTION 'Only the RFQ owner can accept an offer';
  END IF;
  IF v_rfq.status <> 'published' THEN
    RAISE EXCEPTION 'RFQ is not open';
  END IF;

  UPDATE public.offers SET status = 'accepted' WHERE id = _offer_id;
  UPDATE public.offers SET status = 'rejected'
    WHERE rfq_id = v_rfq.id AND id <> _offer_id AND status = 'submitted';
  UPDATE public.rfqs SET status = 'accepted' WHERE id = v_rfq.id;

  INSERT INTO public.marketplace_orders
    (rfq_id, offer_id, company_id, customer_id, amount, currency)
  VALUES
    (v_rfq.id, _offer_id, v_offer.company_id, v_rfq.customer_id,
     v_offer.price, v_offer.currency)
  RETURNING id INTO v_order_id;

  INSERT INTO public.audit_log (actor_id, action, entity_type, entity_id, data)
  VALUES (auth.uid(), 'offer.accepted', 'offer', _offer_id,
          jsonb_build_object('order_id', v_order_id, 'rfq_id', v_rfq.id));

  RETURN v_order_id;
END;
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
ALTER TABLE public.verticals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rfqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rfq_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.verification_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

-- Catalog: public read, writes via service role only
CREATE POLICY "Verticals are public" ON public.verticals
  FOR SELECT USING (true);
CREATE POLICY "Categories are public" ON public.categories
  FOR SELECT USING (true);

-- Companies: public directory, members manage
CREATE POLICY "Company profiles are public" ON public.companies
  FOR SELECT USING (true);
CREATE POLICY "Users can create their company" ON public.companies
  FOR INSERT WITH CHECK (owner_id = auth.uid());
CREATE POLICY "Members can update their company" ON public.companies
  FOR UPDATE USING (public.is_company_member(id))
  WITH CHECK (public.is_company_member(id));
CREATE POLICY "Owner can delete their company" ON public.companies
  FOR DELETE USING (owner_id = auth.uid());

CREATE POLICY "Members visible to company members" ON public.company_members
  FOR SELECT USING (user_id = auth.uid() OR public.is_company_member(company_id));
CREATE POLICY "Company admins manage members" ON public.company_members
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.companies c
            WHERE c.id = company_id AND c.owner_id = auth.uid())
  );

CREATE POLICY "Company services are public" ON public.company_services
  FOR SELECT USING (true);
CREATE POLICY "Members manage company services" ON public.company_services
  FOR ALL USING (public.is_company_member(company_id));

CREATE POLICY "Portfolio is public" ON public.portfolio_items
  FOR SELECT USING (true);
CREATE POLICY "Members manage portfolio" ON public.portfolio_items
  FOR ALL USING (public.is_company_member(company_id));

-- RFQs: published RFQs visible to signed-in users (companies browse leads);
-- owners always see their own.
CREATE POLICY "Published RFQs visible to authenticated users" ON public.rfqs
  FOR SELECT USING (
    customer_id = auth.uid()
    OR (status = 'published' AND auth.uid() IS NOT NULL)
    OR EXISTS (SELECT 1 FROM public.offers o
               WHERE o.rfq_id = rfqs.id AND public.is_company_member(o.company_id))
  );
CREATE POLICY "Customers create their own RFQs" ON public.rfqs
  FOR INSERT WITH CHECK (customer_id = auth.uid());
CREATE POLICY "Customers update their own RFQs" ON public.rfqs
  FOR UPDATE USING (customer_id = auth.uid());
CREATE POLICY "Customers delete their own RFQs" ON public.rfqs
  FOR DELETE USING (customer_id = auth.uid());

CREATE POLICY "RFQ images follow RFQ visibility" ON public.rfq_images
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.rfqs r WHERE r.id = rfq_id)
  );
CREATE POLICY "RFQ owner manages images" ON public.rfq_images
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.rfqs r
            WHERE r.id = rfq_id AND r.customer_id = auth.uid())
  );

-- Offers: visible to the RFQ owner and the offering company
CREATE POLICY "Offer parties can view offers" ON public.offers
  FOR SELECT USING (
    public.is_company_member(company_id)
    OR EXISTS (SELECT 1 FROM public.rfqs r
               WHERE r.id = rfq_id AND r.customer_id = auth.uid())
  );
CREATE POLICY "Company members submit offers" ON public.offers
  FOR INSERT WITH CHECK (public.is_company_member(company_id));
CREATE POLICY "Company members update their offers" ON public.offers
  FOR UPDATE USING (public.is_company_member(company_id));

-- Orders: parties only
CREATE POLICY "Order parties can view orders" ON public.marketplace_orders
  FOR SELECT USING (
    customer_id = auth.uid() OR public.is_company_member(company_id)
  );
CREATE POLICY "Order parties can update orders" ON public.marketplace_orders
  FOR UPDATE USING (
    customer_id = auth.uid() OR public.is_company_member(company_id)
  );

-- Reviews: public read; only the verified customer of a completed order writes
CREATE POLICY "Reviews are public" ON public.reviews
  FOR SELECT USING (true);
CREATE POLICY "Verified customers review completed orders" ON public.reviews
  FOR INSERT WITH CHECK (
    customer_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.marketplace_orders o
      WHERE o.id = order_id
        AND o.customer_id = auth.uid()
        AND o.company_id = reviews.company_id
        AND o.status = 'completed'
    )
  );

-- Messaging: participants only
CREATE POLICY "Participants view conversations" ON public.conversations
  FOR SELECT USING (
    customer_id = auth.uid() OR public.is_company_member(company_id)
  );
CREATE POLICY "Customers start conversations" ON public.conversations
  FOR INSERT WITH CHECK (
    customer_id = auth.uid() OR public.is_company_member(company_id)
  );
CREATE POLICY "Participants view messages" ON public.messages
  FOR SELECT USING (public.is_conversation_participant(conversation_id));
CREATE POLICY "Participants send messages" ON public.messages
  FOR INSERT WITH CHECK (
    sender_id = auth.uid()
    AND public.is_conversation_participant(conversation_id)
  );

-- Verification: company members create/view; approval via back office
CREATE POLICY "Members view verification requests" ON public.verification_requests
  FOR SELECT USING (public.is_company_member(company_id));
CREATE POLICY "Members create verification requests" ON public.verification_requests
  FOR INSERT WITH CHECK (public.is_company_member(company_id));

-- Notifications: own only
CREATE POLICY "Users view their notifications" ON public.notifications
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users update their notifications" ON public.notifications
  FOR UPDATE USING (user_id = auth.uid());

-- Audit log: users may write their own entries; reads via back office
CREATE POLICY "Authenticated users write audit entries" ON public.audit_log
  FOR INSERT WITH CHECK (actor_id = auth.uid());
CREATE POLICY "Admins read audit log" ON public.audit_log
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.user_roles ur
            WHERE ur.user_id = auth.uid() AND ur.role = 'admin')
  );

-- ---------------------------------------------------------------------------
-- Media buckets
-- ---------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public)
VALUES ('company-media', 'company-media', true),
       ('rfq-media', 'rfq-media', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Company media is public" ON storage.objects
  FOR SELECT USING (bucket_id IN ('company-media', 'rfq-media'));
CREATE POLICY "Authenticated users upload media" ON storage.objects
  FOR INSERT WITH CHECK (
    bucket_id IN ('company-media', 'rfq-media')
    AND auth.uid() IS NOT NULL
    AND (storage.foldername(name))[1] = auth.uid()::text
  );
CREATE POLICY "Uploaders manage their media" ON storage.objects
  FOR UPDATE USING (
    bucket_id IN ('company-media', 'rfq-media')
    AND (storage.foldername(name))[1] = auth.uid()::text
  );
CREATE POLICY "Uploaders delete their media" ON storage.objects
  FOR DELETE USING (
    bucket_id IN ('company-media', 'rfq-media')
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- ---------------------------------------------------------------------------
-- Seed: Phase 1 verticals & categories
-- ---------------------------------------------------------------------------
INSERT INTO public.verticals (slug, name, description, icon, sort_order) VALUES
  ('construction', 'Construction',
   'Verified construction companies for renovation, building and trade work across Europe.',
   'hard-hat', 1),
  ('automotive', 'Automotive',
   'Verified workshops for body, paint and mechanical vehicle services across Europe.',
   'car', 2);

INSERT INTO public.categories (vertical_id, slug, name, sort_order)
SELECT v.id, c.slug, c.name, c.sort_order
FROM public.verticals v
JOIN (VALUES
  ('construction', 'house-renovation', 'House renovation', 1),
  ('construction', 'roof-replacement', 'Roof replacement', 2),
  ('construction', 'plumbing', 'Plumbing', 3),
  ('construction', 'electrical-work', 'Electrical work', 4),
  ('construction', 'painting', 'Painting', 5),
  ('construction', 'flooring', 'Flooring', 6),
  ('construction', 'carpentry', 'Carpentry', 7),
  ('construction', 'masonry', 'Masonry & concrete', 8),
  ('construction', 'windows-doors', 'Windows & doors', 9),
  ('construction', 'landscaping', 'Landscaping & groundwork', 10),
  ('automotive', 'paint-work', 'Paint work', 1),
  ('automotive', 'body-repair', 'Body repair', 2),
  ('automotive', 'collision-repair', 'Collision repair', 3),
  ('automotive', 'dent-removal', 'Dent removal', 4),
  ('automotive', 'rust-repair', 'Rust repair', 5),
  ('automotive', 'smart-repair', 'Smart repair', 6),
  ('automotive', 'wheel-refurbishment', 'Wheel refurbishment', 7),
  ('automotive', 'detailing', 'Detailing', 8),
  ('automotive', 'ceramic-coating', 'Ceramic coating', 9),
  ('automotive', 'wrapping', 'Wrapping', 10),
  ('automotive', 'ppf', 'Paint protection film (PPF)', 11),
  ('automotive', 'windshield-replacement', 'Windshield replacement', 12),
  ('automotive', 'mechanical-repairs', 'Mechanical repairs', 13),
  ('automotive', 'diagnostics', 'Diagnostics', 14),
  ('automotive', 'service', 'Service & maintenance', 15),
  ('automotive', 'engine-rebuild', 'Engine rebuild', 16),
  ('automotive', 'transmission-work', 'Transmission work', 17)
) AS c(vertical_slug, slug, name, sort_order)
ON v.slug = c.vertical_slug;
