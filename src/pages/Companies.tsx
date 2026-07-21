import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import SiteLayout from "@/components/layout/SiteLayout";
import CompanyCard from "@/components/marketplace/CompanyCard";
import EmptyState from "@/components/marketplace/EmptyState";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listCompanies } from "@/modules/companies/api";
import type { CompanySort } from "@/modules/companies/types";
import { listCategories, listVerticals } from "@/modules/marketplace/api";
import { COUNTRIES, LANGUAGES } from "@/modules/core/countries";
import { Building2, Search } from "lucide-react";

const ALL = "all";

export default function Companies() {
  const [params, setParams] = useSearchParams();
  const verticalSlug = params.get("vertical") ?? ALL;
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState(ALL);
  const [categoryId, setCategoryId] = useState(ALL);
  const [language, setLanguage] = useState(ALL);
  const [sort, setSort] = useState<CompanySort>("trust");
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  const { data: verticals } = useQuery({
    queryKey: ["verticals"],
    queryFn: listVerticals,
  });

  const selectedVertical = useMemo(
    () => verticals?.find((v) => v.slug === verticalSlug),
    [verticals, verticalSlug],
  );

  const { data: categories } = useQuery({
    queryKey: ["categories", selectedVertical?.id ?? ALL],
    queryFn: () => listCategories(selectedVertical?.id),
  });

  const { data: companies, isLoading } = useQuery({
    queryKey: ["companies", search, country, categoryId, language, sort, verifiedOnly],
    queryFn: () =>
      listCompanies({
        search: search || undefined,
        country: country === ALL ? undefined : country,
        categoryId: categoryId === ALL ? undefined : categoryId,
        language: language === ALL ? undefined : language,
        sort,
        verifiedOnly,
      }),
  });

  return (
    <SiteLayout>
      <div className="border-b bg-card">
        <div className="container mx-auto px-4 py-10">
          <h1 className="text-3xl font-bold">
            {selectedVertical ? `${selectedVertical.name} companies` : "Find companies"}
          </h1>
          <p className="mt-1 text-muted-foreground">
            Verified professionals across Europe, ranked by trust score.
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        {/* Filters */}
        <div className="grid gap-3 md:grid-cols-5">
          <div className="relative md:col-span-2">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search companies…"
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Select
            value={verticalSlug}
            onValueChange={(v) => {
              setCategoryId(ALL);
              setParams(v === ALL ? {} : { vertical: v });
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Marketplace" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All marketplaces</SelectItem>
              {verticals?.map((v) => (
                <SelectItem key={v.id} value={v.slug}>{v.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={categoryId} onValueChange={setCategoryId}>
            <SelectTrigger>
              <SelectValue placeholder="Service" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All services</SelectItem>
              {categories?.map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger>
              <SelectValue placeholder="Country" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All countries</SelectItem>
              {COUNTRIES.map((c) => (
                <SelectItem key={c.code} value={c.code}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-2">
            <Checkbox
              id="verified"
              checked={verifiedOnly}
              onCheckedChange={(v) => setVerifiedOnly(v === true)}
            />
            <Label htmlFor="verified" className="text-sm font-normal">
              Verified companies only
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-sm font-normal text-muted-foreground">Language</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="h-8 w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Any language</SelectItem>
                {LANGUAGES.map((l) => (
                  <SelectItem key={l.code} value={l.code}>{l.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-sm font-normal text-muted-foreground">Sort by</Label>
            <Select value={sort} onValueChange={(v) => setSort(v as CompanySort)}>
              <SelectTrigger className="h-8 w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="trust">Trust score</SelectItem>
                <SelectItem value="rating">Rating</SelectItem>
                <SelectItem value="newest">Newest</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Results */}
        <div className="mt-8">
          {isLoading ? (
            <p className="text-muted-foreground">Loading companies…</p>
          ) : companies && companies.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {companies.map((company) => (
                <CompanyCard key={company.id} company={company} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={Building2}
              title="No companies found"
              description="Try adjusting your filters — or be the first company in this segment."
            />
          )}
        </div>
      </div>
    </SiteLayout>
  );
}
