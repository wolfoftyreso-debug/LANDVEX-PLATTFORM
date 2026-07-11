
REVOKE EXECUTE ON FUNCTION public.has_active_kaka_subscription(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.has_active_kaka_subscription(UUID) TO service_role;
