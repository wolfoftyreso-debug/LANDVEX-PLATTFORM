import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useOrders, Order } from "@/hooks/useAdminData";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";
import { sv } from "date-fns/locale";
import { Search } from "lucide-react";

const statusColors: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-700 border-yellow-500/30",
  processing: "bg-blue-500/20 text-blue-700 border-blue-500/30",
  completed: "bg-green-500/20 text-green-700 border-green-500/30",
  cancelled: "bg-red-500/20 text-red-700 border-red-500/30",
};

const statusLabels: Record<string, string> = {
  pending: "Väntande",
  processing: "Behandlas",
  completed: "Slutförd",
  cancelled: "Avbruten",
};

export function OrdersTable() {
  const { data: orders, isLoading } = useOrders();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filteredOrders = orders?.filter((order) => {
    const matchesSearch =
      order.order_number.toLowerCase().includes(search.toLowerCase()) ||
      order.customer_email.toLowerCase().includes(search.toLowerCase()) ||
      order.customer_name?.toLowerCase().includes(search.toLowerCase());
    
    const matchesStatus = statusFilter === "all" || order.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Sök ordernummer, email eller namn..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full sm:w-[180px]">
            <SelectValue placeholder="Filtrera status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alla statusar</SelectItem>
            <SelectItem value="pending">Väntande</SelectItem>
            <SelectItem value="processing">Behandlas</SelectItem>
            <SelectItem value="completed">Slutförd</SelectItem>
            <SelectItem value="cancelled">Avbruten</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ordernummer</TableHead>
              <TableHead>Kund</TableHead>
              <TableHead>Datum</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Belopp</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredOrders?.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                  Inga ordrar hittades
                </TableCell>
              </TableRow>
            ) : (
              filteredOrders?.map((order) => (
                <TableRow key={order.id}>
                  <TableCell className="font-medium">{order.order_number}</TableCell>
                  <TableCell>
                    <div>
                      <div className="font-medium">{order.customer_name || "—"}</div>
                      <div className="text-sm text-muted-foreground">{order.customer_email}</div>
                    </div>
                  </TableCell>
                  <TableCell>
                    {format(new Date(order.created_at), "d MMM yyyy, HH:mm", { locale: sv })}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={statusColors[order.status] || ""}>
                      {statusLabels[order.status] || order.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {Number(order.total_amount).toLocaleString("sv-SE")} {order.currency}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
