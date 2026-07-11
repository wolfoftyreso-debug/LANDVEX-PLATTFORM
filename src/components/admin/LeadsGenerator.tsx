import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Sparkles, RefreshCw, Building2, Users, MapPin, Mail, Search, Copy, Check, Send } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";

interface Lead {
  company_name: string;
  industry: string;
  employee_count: number;
  district: string;
  reason: string;
}

interface EmailContent {
  subject: string;
  body: string;
  personalization_points: string[];
}

interface ResearchResult {
  company_name: string;
  research_summary: string;
  email: EmailContent;
}

export function LeadsGenerator() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [researchingLead, setResearchingLead] = useState<string | null>(null);
  const [emailDialog, setEmailDialog] = useState<ResearchResult | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [recipient, setRecipient] = useState("");
  const [sending, setSending] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    setRecipient("");
  }, [emailDialog?.company_name]);

  const sendEmail = async () => {
    if (!emailDialog || !recipient) return;
    setSending(true);
    try {
      const res = await fetch(
        `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/send-outreach-email`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY}`,
          },
          body: JSON.stringify({
            to_email: recipient,
            to_name: emailDialog.company_name,
            subject: emailDialog.email.subject,
            body: emailDialog.email.body,
          }),
        },
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Kunde inte skicka mejl");
      toast({
        title: "Mejl skickat!",
        description: `Skickat från konditorivaror@gmail.com till ${recipient}`,
      });
      setEmailDialog(null);
    } catch (err) {
      toast({
        title: "Fel vid utskick",
        description: err instanceof Error ? err.message : "Okänt fel",
        variant: "destructive",
      });
    } finally {
      setSending(false);
    }
  };

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

  const researchCompany = async (lead: Lead) => {
    setResearchingLead(lead.company_name);
    try {
      const response = await fetch(
        `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/research-company`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY}`,
          },
          body: JSON.stringify({
            company_name: lead.company_name,
            district: lead.district,
            industry: lead.industry,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Kunde inte researcha företaget");
      }

      const data: ResearchResult = await response.json();
      setEmailDialog(data);
      toast({
        title: "Research klar!",
        description: `Personligt mejl genererat för ${lead.company_name}`,
      });
    } catch (error) {
      console.error("Error researching company:", error);
      toast({
        title: "Fel",
        description: error instanceof Error ? error.message : "Kunde inte researcha företaget",
        variant: "destructive",
      });
    } finally {
      setResearchingLead(null);
    }
  };

  const copyToClipboard = async (text: string, field: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
    toast({
      title: "Kopierat!",
      description: `${field} kopierat till urklipp`,
    });
  };

  const getEmployeeCountBadge = (count: number) => {
    if (count >= 100) return "bg-green-100 text-green-800";
    if (count >= 50) return "bg-blue-100 text-blue-800";
    if (count >= 25) return "bg-yellow-100 text-yellow-800";
    return "bg-gray-100 text-gray-800";
  };

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                AI Kundprospektering
              </CardTitle>
              <CardDescription>
                Generera leads och skapa personliga mejl med AI-driven research
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
                    <TableHead className="text-right">Åtgärd</TableHead>
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
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => researchCompany(lead)}
                          disabled={researchingLead === lead.company_name}
                        >
                          {researchingLead === lead.company_name ? (
                            <>
                              <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                              Researchar...
                            </>
                          ) : (
                            <>
                              <Search className="h-3 w-3 mr-1" />
                              Research & Mejl
                            </>
                          )}
                        </Button>
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

      <Dialog open={!!emailDialog} onOpenChange={() => setEmailDialog(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5" />
              Personligt mejl för {emailDialog?.company_name}
            </DialogTitle>
            <DialogDescription>
              AI-genererat mejl baserat på företagsresearch
            </DialogDescription>
          </DialogHeader>
          
          {emailDialog && (
            <div className="space-y-4">
              {emailDialog.research_summary && (
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Research-sammanfattning:</p>
                  <p className="text-sm">{emailDialog.research_summary.substring(0, 300)}...</p>
                </div>
              )}

              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-sm font-medium">Ämnesrad:</label>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => copyToClipboard(emailDialog.email.subject, "Ämnesrad")}
                    >
                      {copiedField === "Ämnesrad" ? (
                        <Check className="h-3 w-3" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                  <div className="p-3 bg-background border rounded-md">
                    <p className="font-medium">{emailDialog.email.subject}</p>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-sm font-medium">Mejltext:</label>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => copyToClipboard(emailDialog.email.body, "Mejltext")}
                    >
                      {copiedField === "Mejltext" ? (
                        <Check className="h-3 w-3" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                  <div className="p-3 bg-background border rounded-md whitespace-pre-wrap">
                    {emailDialog.email.body}
                  </div>
                </div>

                {emailDialog.email.personalization_points?.length > 0 && (
                  <div>
                    <label className="text-sm font-medium mb-2 block">Personaliseringspunkter:</label>
                    <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                      {emailDialog.email.personalization_points.map((point, i) => (
                        <li key={i}>{point}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="pt-4 border-t space-y-2">
                  <label className="text-sm font-medium">Skicka till (mottagarens mejl):</label>
                  <div className="flex gap-2">
                    <Input
                      type="email"
                      placeholder="kontakt@företag.se"
                      value={recipient}
                      onChange={(e) => setRecipient(e.target.value)}
                      disabled={sending}
                    />
                    <Button
                      onClick={sendEmail}
                      disabled={sending || !recipient || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient)}
                    >
                      {sending ? (
                        <><RefreshCw className="h-4 w-4 mr-2 animate-spin" /> Skickar...</>
                      ) : (
                        <><Send className="h-4 w-4 mr-2" /> Skicka mejl</>
                      )}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Skickas från <strong>konditorivaror@gmail.com</strong> som Tiffany.
                  </p>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
