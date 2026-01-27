import { useState } from "react";
import { LogIn, LogOut } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import AuthDialog from "./AuthDialog";

const AccountMenu = () => {
  const { user, loading, signOut } = useAuth();
  const [authDialogOpen, setAuthDialogOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");

  const handleOpenAuth = (mode: "login" | "signup") => {
    setAuthMode(mode);
    setAuthDialogOpen(true);
  };

  const handleSignOut = async () => {
    await signOut();
  };

  if (loading) {
    return null;
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="text-primary hover:text-primary/80 font-serif text-base font-bold border-2 hover:bg-[rgba(220,38,38,0.3)]"
            style={{ borderColor: '#dc2626' }}
          >
            Mitt konto
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="bg-background border border-border shadow-lg z-50 min-w-[160px]"
        >
          {user ? (
            <>
              <DropdownMenuItem className="text-muted-foreground text-sm cursor-default">
                {user.email}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={handleSignOut}
                className="cursor-pointer flex items-center gap-2"
              >
                <LogOut className="h-4 w-4" />
                Logga ut
              </DropdownMenuItem>
            </>
          ) : (
            <>
              <div className="px-1 py-1">
                <button
                  onClick={() => handleOpenAuth("signup")}
                  className="w-full px-3 py-2 text-left rounded-md hover:bg-[rgba(220,38,38,0.3)] focus:bg-[rgba(220,38,38,0.3)] transition-colors"
                >
                  Skapa konto
                </button>
              </div>
              <DropdownMenuItem
                onClick={() => handleOpenAuth("login")}
                className="cursor-pointer hover:!bg-[rgba(220,38,38,0.3)] focus:!bg-[rgba(220,38,38,0.3)]"
              >
                Logga in
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <AuthDialog
        open={authDialogOpen}
        onOpenChange={setAuthDialogOpen}
        mode={authMode}
        onModeChange={setAuthMode}
      />
    </>
  );
};

export default AccountMenu;
