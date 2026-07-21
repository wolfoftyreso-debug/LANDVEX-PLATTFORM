import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
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
  addPortfolioItem,
  getMyCompany,
  listCompanyServices,
  listPortfolio,
  setCompanyServices,
  updateCompany,
  uploadMedia,
} from "@/modules/companies/api";
import { listCategories, listVerticals } from "@/modules/marketplace/api";
import { LANGUAGES } from "@/modules/core/countries";
import type { AvailabilityStatus } from "@/modules/core/types";
import { toast } from "sonner";
import { ImagePlus, Upload } from "lucide-react";

export default function CompanyEdit() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, loading } = useAuth();

  const { data: company, isLoading: companyLoading } = useQuery({
    queryKey: ["my-company"],
    queryFn: getMyCompany,
    enabled: !!user,
  });

  const { data: verticals } = useQuery({ queryKey: ["verticals"], queryFn: listVerticals });
  const { data: categories } = useQuery({
    queryKey: ["categories-all"],
    queryFn: () => listCategories(),
  });
  const { data: services } = useQuery({
    queryKey: ["company-services", company?.id],
    queryFn: () => listCompanyServices(company!.id),
    enabled: !!company,
  });
  const { data: portfolio } = useQuery({
    queryKey: ["company-portfolio", company?.id],
    queryFn: () => listPortfolio(company!.id),
    enabled: !!company,
  });

  const [form, setForm] = useState({
    description: "",
    city: "",
    website: "",
    contact_email: "",
    contact_phone: "",
    availability: "available" as AvailabilityStatus,
    languages: [] as string[],
    certifications: "",
  });
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [portfolioTitle, setPortfolioTitle] = useState("");
  const [portfolioDescription, setPortfolioDescription] = useState("");
  const [portfolioFile, setPortfolioFile] = useState<File | null>(null);

  useEffect(() => {
    if (company) {
      setForm({
        description: company.description ?? "",
        city: company.city ?? "",
        website: company.website ?? "",
        contact_email: company.contact_email ?? "",
        contact_phone: company.contact_phone ?? "",
        availability: company.availability,
        languages: company.languages,
        certifications: company.certifications.join(", "),
      });
    }
  }, [company]);

  useEffect(() => {
    if (services) setSelectedCategories(services.map((s) => s.category_id));
  }, [services]);

  const save = useMutation({
    mutationFn: async () => {
      await updateCompany(company!.id, {
        description: form.description || undefined,
        city: form.city || undefined,
        website: form.website || undefined,
        contact_email: form.contact_email || undefined,
        contact_phone: form.contact_phone || undefined,
        availability: form.availability,
        languages: form.languages,
        certifications: form.certifications
          .split(",")
          .map((c) => c.trim())
          .filter(Boolean),
      });
      await setCompanyServices(company!.id, selectedCategories);
    },
    onSuccess: () => {
      toast.success("Profile updated.");
      queryClient.invalidateQueries({ queryKey: ["my-company"] });
      queryClient.invalidateQueries({ queryKey: ["company-services", company?.id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const uploadImage = useMutation({
    mutationFn: async ({ file, field }: { file: File; field: "logo_url" | "cover_url" }) => {
      const url = await uploadMedia("company-media", file);
      await updateCompany(company!.id, { [field]: url });
    },
    onSuccess: () => {
      toast.success("Image updated.");
      queryClient.invalidateQueries({ queryKey: ["my-company"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const addPortfolio = useMutation({
    mutationFn: async () => {
      let imageUrl: string | undefined;
      if (portfolioFile) imageUrl = await uploadMedia("company-media", portfolioFile);
      await addPortfolioItem(company!.id, {
        title: portfolioTitle,
        description: portfolioDescription || undefined,
        image_url: imageUrl,
      });
    },
    onSuccess: () => {
      toast.success("Portfolio item added.");
      setPortfolioTitle("");
      setPortfolioDescription("");
      setPortfolioFile(null);
      queryClient.invalidateQueries({ queryKey: ["company-portfolio", company?.id] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (!loading && !user) {
    navigate("/auth?next=/company/edit");
    return null;
  }

  if (!companyLoading && !company) {
    navigate("/company/register");
    return null;
  }

  if (!company) {
    return (
      <SiteLayout>
        <div className="container mx-auto px-4 py-16 text-muted-foreground">Loading…</div>
      </SiteLayout>
    );
  }

  const toggleCategory = (id: string) =>
    setSelectedCategories((current) =>
      current.includes(id) ? current.filter((c) => c !== id) : [...current, id],
    );

  const toggleLanguage = (code: string) =>
    setForm((f) => ({
      ...f,
      languages: f.languages.includes(code)
        ? f.languages.filter((l) => l !== code)
        : [...f.languages, code],
    }));

  return (
    <SiteLayout>
      <div className="container mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-3xl font-bold">Edit company profile</h1>
        <p className="mt-1 text-muted-foreground">
          Public profile: <span className="font-mono text-xs">/company/{company.slug}</span>
        </p>

        {/* Branding */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Branding</CardTitle>
            <CardDescription>Logo and cover image for your profile page.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-3">
              <Avatar className="h-16 w-16 rounded-xl">
                <AvatarImage src={company.logo_url ?? undefined} />
                <AvatarFallback className="rounded-xl bg-primary/10 font-bold text-primary">
                  {company.name.slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <label className="cursor-pointer">
                <span className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
                  <Upload className="h-4 w-4" /> Change logo
                </span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) uploadImage.mutate({ file, field: "logo_url" });
                  }}
                />
              </label>
            </div>
            <label className="cursor-pointer">
              <span className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
                <ImagePlus className="h-4 w-4" /> Change cover image
              </span>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadImage.mutate({ file, field: "cover_url" });
                }}
              />
            </label>
          </CardContent>
        </Card>

        {/* Details */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Profile details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                rows={4}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>City</Label>
                <Input value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Availability</Label>
                <Select
                  value={form.availability}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, availability: v as AvailabilityStatus }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="available">Available for work</SelectItem>
                    <SelectItem value="busy">Limited availability</SelectItem>
                    <SelectItem value="unavailable">Unavailable</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Website</Label>
                <Input value={form.website} onChange={(e) => setForm((f) => ({ ...f, website: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Contact email</Label>
                <Input value={form.contact_email} onChange={(e) => setForm((f) => ({ ...f, contact_email: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Contact phone</Label>
                <Input value={form.contact_phone} onChange={(e) => setForm((f) => ({ ...f, contact_phone: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Certifications (comma-separated)</Label>
                <Input
                  placeholder="ISO 9001, Safe Contractor…"
                  value={form.certifications}
                  onChange={(e) => setForm((f) => ({ ...f, certifications: e.target.value }))}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Languages</Label>
              <div className="flex flex-wrap gap-1.5">
                {LANGUAGES.map((l) => (
                  <Badge
                    key={l.code}
                    variant={form.languages.includes(l.code) ? "default" : "outline"}
                    className="cursor-pointer select-none"
                    onClick={() => toggleLanguage(l.code)}
                  >
                    {l.name}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Services</Label>
              <div className="space-y-3">
                {verticals?.map((v) => (
                  <div key={v.id}>
                    <div className="text-xs font-semibold uppercase text-muted-foreground">{v.name}</div>
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

            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save changes"}
            </Button>
          </CardContent>
        </Card>

        {/* Portfolio */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Portfolio</CardTitle>
            <CardDescription>
              Show completed projects — profiles with references win more work.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {portfolio && portfolio.length > 0 && (
              <div className="grid gap-3 sm:grid-cols-2">
                {portfolio.map((item) => (
                  <div key={item.id} className="rounded-lg border p-3">
                    {item.image_url && (
                      <img
                        src={item.image_url}
                        alt={item.title}
                        className="mb-2 h-28 w-full rounded object-cover"
                      />
                    )}
                    <div className="text-sm font-medium">{item.title}</div>
                  </div>
                ))}
              </div>
            )}
            <div className="space-y-2 rounded-lg border border-dashed p-4">
              <Label>Add project</Label>
              <Input
                placeholder="Project title"
                value={portfolioTitle}
                onChange={(e) => setPortfolioTitle(e.target.value)}
              />
              <Textarea
                rows={2}
                placeholder="Short description"
                value={portfolioDescription}
                onChange={(e) => setPortfolioDescription(e.target.value)}
              />
              <Input
                type="file"
                accept="image/*"
                onChange={(e) => setPortfolioFile(e.target.files?.[0] ?? null)}
              />
              <Button
                size="sm"
                disabled={!portfolioTitle.trim() || addPortfolio.isPending}
                onClick={() => addPortfolio.mutate()}
              >
                {addPortfolio.isPending ? "Adding…" : "Add to portfolio"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </SiteLayout>
  );
}
