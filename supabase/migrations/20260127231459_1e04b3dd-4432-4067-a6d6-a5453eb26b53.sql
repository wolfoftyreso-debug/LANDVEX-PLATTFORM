-- Add company_name column to profiles table
ALTER TABLE public.profiles
ADD COLUMN company_name text;