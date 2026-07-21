-- ============================================================================
-- BALTIC BRIDGE — New verticals: Bakery & Food Production, Manufacturing
-- Proof of the generic marketplace engine: a new vertical is data only.
-- No core tables, functions, triggers or policies change.
-- ============================================================================

INSERT INTO public.verticals (slug, name, description, icon, sort_order) VALUES
  ('food-production', 'Bakery & Food',
   'Bakeries, confectioneries and food producers taking custom and wholesale orders across Europe.',
   'croissant', 3),
  ('manufacturing', 'Manufacturing',
   'Workshops and factories for custom production — from one-off prototypes to serial manufacturing.',
   'factory', 4);

INSERT INTO public.categories (vertical_id, slug, name, sort_order)
SELECT v.id, c.slug, c.name, c.sort_order
FROM public.verticals v
JOIN (VALUES
  -- Bakery & Food Production
  ('food-production', 'bread-bakery', 'Bread & bakery goods', 1),
  ('food-production', 'pastries-viennoiserie', 'Pastries & viennoiserie', 2),
  ('food-production', 'custom-cakes', 'Custom & celebration cakes', 3),
  ('food-production', 'confectionery', 'Confectionery & chocolate', 4),
  ('food-production', 'catering', 'Catering & event food', 5),
  ('food-production', 'wholesale-baked-goods', 'Wholesale baked goods', 6),
  ('food-production', 'private-label-food', 'Private label & contract production', 7),
  ('food-production', 'specialty-diets', 'Gluten-free / vegan / specialty diets', 8),
  ('food-production', 'beverages', 'Beverage production', 9),
  ('food-production', 'preserves-deli', 'Preserves & deli products', 10),
  -- Manufacturing
  ('manufacturing', 'cnc-machining', 'CNC machining', 1),
  ('manufacturing', 'metal-fabrication', 'Metal fabrication & welding', 2),
  ('manufacturing', 'sheet-metal', 'Sheet metal work', 3),
  ('manufacturing', 'injection-molding', 'Plastics & injection molding', 4),
  ('manufacturing', '3d-printing', '3D printing & prototyping', 5),
  ('manufacturing', 'woodworking', 'Woodworking & furniture', 6),
  ('manufacturing', 'textiles-sewing', 'Textiles & sewing production', 7),
  ('manufacturing', 'electronics-assembly', 'Electronics assembly', 8),
  ('manufacturing', 'packaging', 'Packaging production', 9),
  ('manufacturing', 'surface-treatment', 'Surface treatment & coating', 10),
  ('manufacturing', 'tooling-molds', 'Tooling & molds', 11),
  ('manufacturing', 'assembly-services', 'Assembly & kitting services', 12)
) AS c(vertical_slug, slug, name, sort_order)
ON v.slug = c.vertical_slug;
