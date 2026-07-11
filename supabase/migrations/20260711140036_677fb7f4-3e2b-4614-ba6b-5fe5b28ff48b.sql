-- Restrict direct execution of SECURITY DEFINER function has_role.
-- Switching to SECURITY INVOKER: when called as auth.uid() the user_roles
-- RLS policy already lets a user see (only) their own role rows, so
-- has_role(auth.uid(), 'admin') still returns correctly.
-- We also revoke EXECUTE from anon/public so the function cannot be
-- invoked directly from the Data API.

CREATE OR REPLACE FUNCTION public.has_role(_user_id uuid, _role app_role)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_roles
    WHERE user_id = _user_id
      AND role = _role
  )
$$;

REVOKE EXECUTE ON FUNCTION public.has_role(uuid, app_role) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.has_role(uuid, app_role) FROM anon;
-- authenticated retains EXECUTE so RLS policies referencing has_role
-- continue to work; the function itself is now SECURITY INVOKER so it
-- cannot be used to bypass RLS.
GRANT EXECUTE ON FUNCTION public.has_role(uuid, app_role) TO authenticated;
GRANT EXECUTE ON FUNCTION public.has_role(uuid, app_role) TO service_role;