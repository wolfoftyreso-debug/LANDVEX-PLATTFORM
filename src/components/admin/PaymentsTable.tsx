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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePayments } from "@/hooks/useAdminData";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";
import { sv } from "date-fns/locale";

const statusColors: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-700 border-yellow-500/30",
  completed: "bg-green-500/20 text-green-700 border-green-500/30",
  failed: "bg-red-500/20 text-red-700 border-red-500/30",
  refunded: "bg-purple-500/20 text-purple-700 border-purple-500/30",
};

const statusLabels: Record<string, string> = {
  pending: "Väntande",
  completed: "Genomförd",
  failed: "Misslyckad",
  refunded: "Återbetald",
};

export function PaymentsTable() {
  const { data: payments, isLoading } = usePayments();
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filteredPayments = payments?.filter((payment) => {
    return statusFilter === "all" || payment.status === statusFilter;
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
      <div className="flex">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filtrera status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alla statusar</SelectItem>
            <SelectItem value="pending">Väntande</SelectItem>
            <SelectItem value="completed">Genomförd</SelectItem>
            <SelectItem value="failed">Misslyckad</SelectItem>
            <SelectItem value="refunded">Återbetald</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Betalnings-ID</TableHead>
              <TableHead>Betalmetod</TableHead>
              <TableHead>Datum</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Belopp</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredPayments?.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                  Inga betalningar hittades
                </TableCell>
              </TableRow>
            ) : (
              filteredPayments?.map((payment) => (
                <TableRow key={payment.id}>
                  <TableCell className="font-mono text-sm">
                    {payment.id.slice(0, 8)}...
                  </TableCell>
                  <TableCell>{payment.payment_method || "—"}</TableCell>
                  <TableCell>
                    {format(new Date(payment.created_at), "d MMM yyyy, HH:mm", { locale: sv })}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={statusColors[payment.status] || ""}>
                      {statusLabels[payment.status] || payment.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {Number(payment.amount).toLocaleString("sv-SE")} {payment.currency}
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
