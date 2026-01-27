import { useState, useEffect } from 'react';
import { storefrontApiRequest, STOREFRONT_PRODUCTS_QUERY, ShopifyProduct } from '@/lib/shopify';

export function useShopifyProducts(query?: string) {
  const [products, setProducts] = useState<ShopifyProduct[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProducts() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await storefrontApiRequest(STOREFRONT_PRODUCTS_QUERY, { 
          first: 10,
          query: query || null
        });
        if (data?.data?.products?.edges) {
          setProducts(data.data.products.edges);
        }
      } catch (err) {
        console.error('Failed to fetch products:', err);
        setError('Kunde inte ladda produkter');
      } finally {
        setIsLoading(false);
      }
    }

    fetchProducts();
  }, [query]);

  return { products, isLoading, error };
}
