import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Sparkles, RefreshCw, Building2, Users, MapPin } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";

interface Lead {
  company_name: string;
  industry: string;
  employee_count: number;
  district: string;
  reason: string;
}

export function LeadsGenerator() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const generateLeads = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/generate-leads`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Kunde inte generera leads");
      }

      const data = await response.json();
      setLeads(data.leads || []);
      toast({
        title: "Leads genererade!",
        description: `${data.leads?.length || 0} potentiella kunder hittades.`,
      });
    } catch (error) {
      console.error("Error generating leads:", error);
      toast({
        title: "Fel",
        description: error instanceof Error ? error.message : "Kunde inte generera leads",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const getEmployeeCountBadge = (count: number) => {
    if (count >= 100) return "bg-green-100 text-green-800";
    if (count >= 50) return "bg-blue-100 text-blue-800";
    if (count >= 25) return "bg-yellow-100 text-yellow-800";
    return "bg-gray-100 text-gray-800";
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              AI Kundprospektering
            </CardTitle>
            <CardDescription>
              Låt AI hitta potentiella B2B-kunder i Storstockholm
            </CardDescription>
          </div>
          <Button onClick={generateLeads} disabled={isLoading}>
            {isLoading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Genererar...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Generera leads
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : leads.length > 0 ? (
          <div className="rounded-md border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <div className="flex items-center gap-1">
                      <Building2 className="h-4 w-4" />
                      Företag
                    </div>
                  </TableHead>
                  <TableHead>Bransch</TableHead>
                  <TableHead>
                    <div className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      Anställda
                    </div>
                  </TableHead>
                  <TableHead>
                    <div className="flex items-center gap-1">
                      <MapPin className="h-4 w-4" />
                      Stadsdel
                    </div>
                  </TableHead>
                  <TableHead>Varför bra kund</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leads.map((lead, index) => (
                  <TableRow key={index}>
                    <TableCell className="font-medium">{lead.company_name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{lead.industry}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={getEmployeeCountBadge(lead.employee_count)}>
                        {lead.employee_count} st
                      </Badge>
                    </TableCell>
                    <TableCell>{lead.district}</TableCell>
                    <TableCell className="max-w-xs text-sm text-muted-foreground">
                      {lead.reason}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Klicka på "Generera leads" för att hitta potentiella kunder</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
