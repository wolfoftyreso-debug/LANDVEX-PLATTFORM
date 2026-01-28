import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

export interface Order {
  id: string;
  order_number: string;
  customer_email: string;
  customer_name: string | null;
  items: any[];
  total_amount: number;
  currency: string;
  status: string;
  created_at: string;
}

export interface Customer {
  id: string;
  email: string;
  name: string | null;
  phone: string | null;
  company: string | null;
  total_orders: number;
  total_spent: number;
  created_at: string;
}

export interface Payment {
  id: string;
  order_id: string | null;
  amount: number;
  currency: string;
  status: string;
  payment_method: string | null;
  created_at: string;
}

export function useOrders() {
  return useQuery({
    queryKey: ["admin-orders"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("orders")
        .select("*")
        .order("created_at", { ascending: false });
      
      if (error) throw error;
      return data as Order[];
    },
  });
}

export function useCustomers() {
  return useQuery({
    queryKey: ["admin-customers"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("customers")
        .select("*")
        .order("created_at", { ascending: false });
      
      if (error) throw error;
      return data as Customer[];
    },
  });
}

export function usePayments() {
  return useQuery({
    queryKey: ["admin-payments"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("payments")
        .select("*")
        .order("created_at", { ascending: false });
      
      if (error) throw error;
      return data as Payment[];
    },
  });
}

export function useAdminStats() {
  return useQuery({
    queryKey: ["admin-stats"],
    queryFn: async () => {
      const [ordersRes, customersRes, paymentsRes] = await Promise.all([
        supabase.from("orders").select("total_amount, status"),
        supabase.from("customers").select("id"),
        supabase.from("payments").select("amount, status"),
      ]);

      const orders = ordersRes.data || [];
      const customers = customersRes.data || [];
      const payments = paymentsRes.data || [];

      const totalRevenue = orders.reduce((sum, o) => sum + Number(o.total_amount), 0);
      const pendingOrders = orders.filter(o => o.status === "pending").length;
      const completedPayments = payments.filter(p => p.status === "completed").length;

      return {
        totalOrders: orders.length,
        totalCustomers: customers.length,
        totalRevenue,
        pendingOrders,
        totalPayments: payments.length,
        completedPayments,
      };
    },
  });
}
