-- Add separate address fields to profiles table
ALTER TABLE public.profiles
ADD COLUMN street_address text,
ADD COLUMN postal_code text,
ADD COLUMN city text;