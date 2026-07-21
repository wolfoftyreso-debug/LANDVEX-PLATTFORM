import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import {
  createCompany,
  getMyCompany,
  setCompanyServices,
  slugify,
} from "@/modules/companies/api";
import { listCategories, listVerticals } from "@/modules/marketplace/api";
import { COUNTRIES, LANGUAGES } from "@/modules/core/countries";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";

export default function CompanyRegister() {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [vatNumber, setVatNumber] = useState("");
  const [orgNumber, setOrgNumber] = useState("");
  const [website, setWebsite] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [yearFounded, setYearFounded] = useState("");
  const [employeeCount, setEmployeeCount] = useState("");
  const [languages, setLanguages] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);

  const { data: existing } = useQuery({
    queryKey: ["my-company"],
    queryFn: getMyCompany,
    enabled: !!user,
  });

  useEffect(() => {
    if (existing) navigate("/dashboard");
  }, [existing, navigate]);

  const { data: verticals } = useQuery({ queryKey: ["verticals"], queryFn: listVerticals });
  const { data: categories } = useQuery({
    queryKey: ["categories-all"],
    queryFn: () => listCategories(),
  });

  const slug = useMemo(() => slugify(name), [name]);

  const submit = useMutation({
    mutationFn: async () => {
      const company = await createCompany({
        name,
        slug: `${slug}-${country.toLowerCase()}`,
        description,
        country,
        city: city || undefined,
        vat_number: vatNumber || undefined,
        org_number: orgNumber || undefined,
        website: website || undefined,
        contact_email: contactEmail || undefined,
        contact_phone: contactPhone || undefined,
        year_founded: yearFounded ? Number(yearFounded) : undefined,
        employee_count: employeeCount ? Number(employeeCount) : undefined,
        languages,
        countries_served: [country],
      });
      await setCompanyServices(company.id, selectedCategories);
      return company;
    },
    onSuccess: (company) => {
      toast.success("Company profile created — welcome to Baltic Bridge!");
      navigate(`/company/${company.slug}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (!authLoading && !user) {
    navigate("/auth?next=/company/register");
    return null;
  }

  const toggleCategory = (id: string) =>
    setSelectedCategories((current) =>
      current.includes(id) ? current.filter((c) => c !== id) : [...current, id],
    );

  const toggleLanguage = (code: string) =>
    setLanguages((current) =>
      current.includes(code) ? current.filter((c) => c !== code) : [...current, code],
    );

  const valid = name.trim().length >= 2 && !!country && selectedCategories.length > 0;

  return (
    <SiteLayout>
      <div className="container mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-3xl font-bold">List your company</h1>
        <p className="mt-1 text-muted-foreground">
          Create your standardized Baltic Bridge profile. Verification unlocks
          higher visibility — start with the basics.
        </p>

        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Company details</CardTitle>
            <CardDescription>
              Your profile gets a permanent URL:{" "}
              <span className="font-mono text-xs">
                balticbridge.com/company/{slug || "your-company"}
                {country ? `-${country.toLowerCase()}` : ""}
              </span>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="name">Company name *</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Country *</Label>
                <Select value={country} onValueChange={setCountry}>
                  <SelectTrigger>
                    <SelectValue placeholder="Country" />
                  </SelectTrigger>
                  <SelectContent>
                    {COUNTRIES.map((c) => (
                      <SelectItem key={c.code} value={c.code}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="city">City</Label>
                <Input id="city" value={city} onChange={(e) => setCity(e.target.value)} />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                rows={4}
                placeholder="What does your company do? What makes you trustworthy?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Services you offer *</Label>
              <div className="space-y-3">
                {verticals?.map((v) => (
                  <div key={v.id}>
                    <div className="text-xs font-semibold uppercase text-muted-foreground">
                      {v.name}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {categories
                        ?.filter((c) => c.vertical_id === v.id)
                        .map((c) => (
                          <Badge
                            key={c.id}
                            variant={selectedCategories.includes(c.id) ? "default" : "outline"}
                            className="cursor-pointer select-none"
                            onClick={() => toggleCategory(c.id)}
                          >
                            {c.name}
                          </Badge>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Languages spoken</Label>
              <div className="flex flex-wrap gap-1.5">
                {LANGUAGES.map((l) => (
                  <Badge
                    key={l.code}
                    variant={languages.includes(l.code) ? "default" : "outline"}
                    className="cursor-pointer select-none"
                    onClick={() => toggleLanguage(l.code)}
                  >
                    {l.name}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="vat">VAT number</Label>
                <Input id="vat" placeholder="e.g. EE123456789" value={vatNumber} onChange={(e) => setVatNumber(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="org">Organization number</Label>
                <Input id="org" value={orgNumber} onChange={(e) => setOrgNumber(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="year">Year founded</Label>
                <Input id="year" type="number" min="1800" max="2100" value={yearFounded} onChange={(e) => setYearFounded(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="employees">Number of employees</Label>
                <Input id="employees" type="number" min="1" value={employeeCount} onChange={(e) => setEmployeeCount(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="website">Website</Label>
                <Input id="website" placeholder="https://…" value={website} onChange={(e) => setWebsite(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact-email">Contact email</Label>
                <Input id="contact-email" type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact-phone">Contact phone</Label>
                <Input id="contact-phone" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} />
              </div>
            </div>

            <div className="rounded-lg border bg-muted/40 p-4 text-sm text-muted-foreground">
              <ShieldCheck className="mb-1 h-4 w-4 text-primary" />
              After registration you can apply for verification (Bronze → Platinum).
              Verified identity and VAT raise your trust score and search ranking.
            </div>

            <Button
              className="w-full"
              size="lg"
              disabled={!valid || submit.isPending}
              onClick={() => submit.mutate()}
            >
              {submit.isPending ? "Creating profile…" : "Create company profile"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </SiteLayout>
  );
}
