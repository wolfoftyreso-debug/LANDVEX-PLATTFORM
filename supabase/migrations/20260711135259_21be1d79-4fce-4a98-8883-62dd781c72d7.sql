
-- Orders: admin-only reads
DROP POLICY IF EXISTS "Authenticated users can view all orders" ON public.orders;
CREATE POLICY "Admins can view orders"
  ON public.orders FOR SELECT
  TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));

-- Customers: admin-only
DROP POLICY IF EXISTS "Authenticated users can manage customers" ON public.customers;
DROP POLICY IF EXISTS "Authenticated users can view customers" ON public.customers;
CREATE POLICY "Admins can view customers"
  ON public.customers FOR SELECT
  TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));
CREATE POLICY "Admins can manage customers"
  ON public.customers FOR ALL
  TO authenticated
  USING (public.has_role(auth.uid(), 'admin'))
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

-- Payments: admin-only reads
DROP POLICY IF EXISTS "Authenticated users can view payments" ON public.payments;
CREATE POLICY "Admins can view payments"
  ON public.payments FOR SELECT
  TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));
