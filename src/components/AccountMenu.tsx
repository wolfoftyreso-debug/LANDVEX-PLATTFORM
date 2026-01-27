import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
  const { user, loading } = useAuth();
  const [authDialogOpen, setAuthDialogOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const navigate = useNavigate();

  const handleOpenAuth = (mode: "login" | "signup") => {
    setAuthMode(mode);
    setAuthDialogOpen(true);
  };

  if (loading) {
    return null;
  }

  // If user is logged in, navigate directly to account page
  if (user) {
    return (
      <Button
        variant="ghost"
        onClick={() => navigate("/account")}
        className="text-primary hover:text-primary/80 font-serif text-base font-bold border-2 hover:bg-[rgba(220,38,38,0.3)]"
        style={{ borderColor: '#dc2626' }}
      >
        Mitt konto
      </Button>
    );
  }

  // If not logged in, show dropdown with login/signup options
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
          <div className="px-2 py-1.5">
            <button
              onClick={() => handleOpenAuth("signup")}
              className="w-full px-2 py-1.5 text-left text-sm rounded-sm hover:bg-[rgba(220,38,38,0.3)] focus:bg-[rgba(220,38,38,0.3)] transition-colors"
            >
              Skapa konto
            </button>
          </div>
          <DropdownMenuItem
            onClick={() => handleOpenAuth("login")}
            className="cursor-pointer hover:!bg-[rgba(220,38,38,0.3)] focus:!bg-[rgba(220,38,38,0.3)] hover:!text-black focus:!text-black"
          >
            Logga in
          </DropdownMenuItem>
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
