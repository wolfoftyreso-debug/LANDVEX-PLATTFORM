import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { VERTICALS, verticalConfig } from "@/modules/marketplace/config";
import { listCategories, listVerticals } from "@/modules/marketplace/api";
import { createRfq } from "@/modules/rfq/api";
import { uploadMedia } from "@/modules/companies/api";
import { COUNTRIES, LANGUAGES } from "@/modules/core/countries";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Upload } from "lucide-react";

export default function RfqNew() {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();

  const [step, setStep] = useState(0);
  const [verticalSlug, setVerticalSlug] = useState<string | null>(null);
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [deadline, setDeadline] = useState("");
  const [language, setLanguage] = useState("");
  const [metadata, setMetadata] = useState<Record<string, string>>({});
  const [files, setFiles] = useState<File[]>([]);

  const { data: verticals } = useQuery({ queryKey: ["verticals"], queryFn: listVerticals });
  const vertical = useMemo(
    () => verticals?.find((v) => v.slug === verticalSlug),
    [verticals, verticalSlug],
  );
  const uiConfig = verticalSlug ? verticalConfig(verticalSlug) : undefined;

  const { data: categories } = useQuery({
    queryKey: ["categories", vertical?.id],
    queryFn: () => listCategories(vertical!.id),
    enabled: !!vertical,
  });

  const submit = useMutation({
    mutationFn: async () => {
      const imageUrls: string[] = [];
      for (const file of files.slice(0, 6)) {
        imageUrls.push(await uploadMedia("rfq-media", file));
      }
      return createRfq(
        {
          vertical_id: vertical!.id,
          category_id: categoryId,
          title,
          description,
          country,
          city: city || undefined,
          address: address || undefined,
          budget_min: budgetMin ? Number(budgetMin) : null,
          budget_max: budgetMax ? Number(budgetMax) : null,
          deadline: deadline || null,
          preferred_language: language || null,
          metadata,
          metadata_schema_version: uiConfig?.metadataSchemaVersion ?? 1,
        },
        imageUrls,
      );
    },
    onSuccess: (rfq) => {
      toast.success("Your request is published — matching companies can now respond.");
      navigate(`/rfq/${rfq.id}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (!authLoading && !user) {
    navigate("/auth?next=/rfq/new");
    return null;
  }

  const canContinueStep0 = !!verticalSlug;
  const canContinueStep1 = title.trim().length >= 5 && description.trim().length >= 20 && !!country;
  const requiredMetadataMissing = (uiConfig?.metadataFields ?? []).some(
    (f) => f.required && !metadata[f.key]?.trim(),
  );

  return (
    <SiteLayout>
      <div className="container mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-3xl font-bold">Request quotes</h1>
        <p className="mt-1 text-muted-foreground">
          Free and without obligation. Verified companies matching your request will respond with offers.
        </p>

        {/* Step 0: vertical */}
        {step === 0 && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>What do you need help with?</CardTitle>
              <CardDescription>Choose a marketplace.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              {VERTICALS.map((v) => (
                <button
                  key={v.slug}
                  type="button"
                  onClick={() => setVerticalSlug(v.slug)}
                  className={`rounded-lg border p-6 text-left transition-colors ${
                    verticalSlug === v.slug
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "hover:border-primary/50"
                  }`}
                >
                  <v.icon className="h-8 w-8 text-primary" />
                  <div className="mt-2 font-semibold">{v.label}</div>
                  <p className="mt-1 text-xs text-muted-foreground">{v.tagline}</p>
                </button>
              ))}
              <div className="sm:col-span-2 flex justify-end">
                <Button disabled={!canContinueStep0} onClick={() => setStep(1)}>
                  Continue <ArrowRight className="ml-1.5 h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 1: core details */}
        {step === 1 && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Describe your project</CardTitle>
              <CardDescription>
                The more detail you give, the better the quotes you receive.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Service</Label>
                <Select value={categoryId ?? ""} onValueChange={setCategoryId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a service category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories?.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  placeholder={uiConfig?.rfqTitlePlaceholder}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  rows={5}
                  placeholder="Describe the work, current condition, materials, access, timing…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Country</Label>
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
                <Label htmlFor="address">Address (shared only with companies you engage)</Label>
                <Input id="address" value={address} onChange={(e) => setAddress(e.target.value)} />
              </div>
              <div className="flex justify-between">
                <Button variant="ghost" onClick={() => setStep(0)}>
                  <ArrowLeft className="mr-1.5 h-4 w-4" /> Back
                </Button>
                <Button disabled={!canContinueStep1} onClick={() => setStep(2)}>
                  Continue <ArrowRight className="ml-1.5 h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: vertical-specific + budget + submit */}
        {step === 2 && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Details & budget</CardTitle>
              <CardDescription>
                {uiConfig?.label}-specific details help companies quote accurately.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {(uiConfig?.metadataFields ?? []).map((field) => (
                <div key={field.key} className="space-y-2">
                  <Label>{field.label}{field.required ? " *" : ""}</Label>
                  {field.type === "textarea" ? (
                    <Textarea
                      rows={3}
                      placeholder={field.placeholder}
                      value={metadata[field.key] ?? ""}
                      onChange={(e) =>
                        setMetadata((m) => ({ ...m, [field.key]: e.target.value }))
                      }
                    />
                  ) : field.type === "select" ? (
                    <Select
                      value={metadata[field.key] ?? ""}
                      onValueChange={(v) => setMetadata((m) => ({ ...m, [field.key]: v }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={field.label} />
                      </SelectTrigger>
                      <SelectContent>
                        {field.options?.map((o) => (
                          <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      type={field.type}
                      placeholder={field.placeholder}
                      value={metadata[field.key] ?? ""}
                      onChange={(e) =>
                        setMetadata((m) => ({ ...m, [field.key]: e.target.value }))
                      }
                    />
                  )}
                </div>
              ))}

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="budget-min">Budget from (EUR)</Label>
                  <Input
                    id="budget-min"
                    type="number"
                    min="0"
                    value={budgetMin}
                    onChange={(e) => setBudgetMin(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="budget-max">Budget to (EUR)</Label>
                  <Input
                    id="budget-max"
                    type="number"
                    min="0"
                    value={budgetMax}
                    onChange={(e) => setBudgetMax(e.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="deadline">Deadline</Label>
                  <Input
                    id="deadline"
                    type="date"
                    value={deadline}
                    onChange={(e) => setDeadline(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Preferred language</Label>
                  <Select value={language} onValueChange={setLanguage}>
                    <SelectTrigger>
                      <SelectValue placeholder="Any language" />
                    </SelectTrigger>
                    <SelectContent>
                      {LANGUAGES.map((l) => (
                        <SelectItem key={l.code} value={l.code}>{l.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="images">Photos (up to 6)</Label>
                <label
                  htmlFor="images"
                  className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-sm text-muted-foreground hover:border-primary/50"
                >
                  <Upload className="h-4 w-4" />
                  {files.length > 0 ? `${files.length} file(s) selected` : "Click to choose images"}
                </label>
                <input
                  id="images"
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, 6))}
                />
              </div>

              <div className="flex justify-between">
                <Button variant="ghost" onClick={() => setStep(1)}>
                  <ArrowLeft className="mr-1.5 h-4 w-4" /> Back
                </Button>
                <Button
                  disabled={requiredMetadataMissing || submit.isPending}
                  onClick={() => submit.mutate()}
                >
                  {submit.isPending ? "Publishing…" : "Publish request"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </SiteLayout>
  );
}
