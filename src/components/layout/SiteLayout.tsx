import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import {
  Building2,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MessagesSquare,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import NotificationsBell from "@/components/marketplace/NotificationsBell";
import { VERTICALS } from "@/modules/marketplace/config";
import type { ReactNode } from "react";

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2">
      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground font-extrabold">
        B
      </span>
      <span className="text-lg font-extrabold tracking-tight">
        Baltic<span className="text-primary">Bridge</span>
      </span>
    </Link>
  );
}

export function SiteHeader() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <div className="flex items-center gap-8">
          <Logo />
          <nav className="hidden items-center gap-6 text-sm font-medium md:flex">
            <Link to="/companies" className="text-muted-foreground transition-colors hover:text-foreground">
              Find companies
            </Link>
            <Link to="/rfq/new" className="text-muted-foreground transition-colors hover:text-foreground">
              Request quotes
            </Link>
            <Link to="/rfqs" className="text-muted-foreground transition-colors hover:text-foreground">
              Browse requests
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-2">
          {user ? (
            <>
              <NotificationsBell />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Messages"
                onClick={() => navigate("/messages")}
              >
                <MessagesSquare className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="sm" onClick={() => navigate("/dashboard")}>
                <LayoutDashboard className="mr-1.5 h-4 w-4" />
                Dashboard
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  await signOut();
                  navigate("/");
                }}
              >
                <LogOut className="mr-1.5 h-4 w-4" />
                Sign out
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" onClick={() => navigate("/auth")}>
                Sign in
              </Button>
              <Button size="sm" className="hidden sm:inline-flex" onClick={() => navigate("/company/register")}>
                <Building2 className="mr-1.5 h-4 w-4" />
                List your company
              </Button>
            </>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild className="md:hidden">
              <Button variant="ghost" size="icon" aria-label="Menu">
                <Menu className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate("/companies")}>
                <Building2 className="mr-2 h-4 w-4" /> Find companies
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate("/rfq/new")}>
                <FileText className="mr-2 h-4 w-4" /> Request quotes
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate("/rfqs")}>
                <FileText className="mr-2 h-4 w-4" /> Browse requests
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t bg-card">
      <div className="container mx-auto grid gap-8 px-4 py-12 md:grid-cols-4">
        <div>
          <Logo />
          <p className="mt-3 text-sm text-muted-foreground">
            Europe's marketplace for verified professional services. We connect
            customers with trusted companies — we never perform the work.
          </p>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold">For customers</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li><Link to="/companies" className="hover:text-foreground">Find companies</Link></li>
            <li><Link to="/rfq/new" className="hover:text-foreground">Request quotes</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold">For companies</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li><Link to="/company/register" className="hover:text-foreground">List your company</Link></li>
            <li><Link to="/rfqs" className="hover:text-foreground">Browse requests</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold">Marketplaces</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            {VERTICALS.map((v) => (
              <li key={v.slug}>
                <Link
                  to={`/companies?vertical=${v.slug}`}
                  className="hover:text-foreground"
                >
                  {v.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t py-4 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} Baltic Bridge — verified companies, transparent trust.
      </div>
    </footer>
  );
}

export default function SiteLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}
