import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Package, Users, CreditCard, TrendingUp } from "lucide-react";
import { useAdminStats } from "@/hooks/useAdminData";
import { Skeleton } from "@/components/ui/skeleton";

export function AdminStats() {
  const { data: stats, isLoading } = useAdminStats();

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const statCards = [
    {
      title: "Totala Ordrar",
      value: stats?.totalOrders || 0,
      icon: Package,
      description: `${stats?.pendingOrders || 0} väntande`,
    },
    {
      title: "Kunder",
      value: stats?.totalCustomers || 0,
      icon: Users,
      description: "Registrerade kunder",
    },
    {
      title: "Betalningar",
      value: stats?.totalPayments || 0,
      icon: CreditCard,
      description: `${stats?.completedPayments || 0} genomförda`,
    },
    {
      title: "Total Omsättning",
      value: `${(stats?.totalRevenue || 0).toLocaleString("sv-SE")} kr`,
      icon: TrendingUp,
      description: "Totalt intjänat",
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {statCards.map((stat) => (
        <Card key={stat.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
            <stat.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stat.value}</div>
            <p className="text-xs text-muted-foreground">{stat.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
