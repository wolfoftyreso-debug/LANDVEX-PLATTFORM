import { useState } from "react";
import { z } from "zod";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";

const authSchema = z.object({
  email: z.string().trim().email({ message: "Ogiltig e-postadress" }).max(255),
  password: z.string().min(6, { message: "Lösenordet måste vara minst 6 tecken" }).max(100),
});

const emailSchema = z.object({
  email: z.string().trim().email({ message: "Ogiltig e-postadress" }).max(255),
});

type AuthMode = "login" | "signup" | "forgot";

interface AuthDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "login" | "signup";
  onModeChange: (mode: "login" | "signup") => void;
}

const AuthDialog = ({ open, onOpenChange, mode: initialMode, onModeChange }: AuthDialogProps) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [internalMode, setInternalMode] = useState<AuthMode>(initialMode);
  const { signIn, signUp, resetPassword } = useAuth();
  const { toast } = useToast();

  // Sync internal mode with external mode prop
  const mode = internalMode === "forgot" ? "forgot" : initialMode;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (internalMode === "forgot") {
      const validation = emailSchema.safeParse({ email });
      if (!validation.success) {
        toast({
          title: "Fel",
          description: validation.error.errors[0].message,
          variant: "destructive",
        });
        return;
      }

      setIsSubmitting(true);
      try {
        const { error } = await resetPassword(email);
        if (error) {
          toast({
            title: "Kunde inte skicka återställningslänk",
            description: error.message,
            variant: "destructive",
          });
        } else {
          toast({
            title: "E-post skickad!",
            description: "Kolla din inkorg för att återställa ditt lösenord.",
          });
          onOpenChange(false);
          resetForm();
        }
      } finally {
        setIsSubmitting(false);
      }
      return;
    }

    const validation = authSchema.safeParse({ email, password });
    if (!validation.success) {
      toast({
        title: "Fel",
        description: validation.error.errors[0].message,
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);

    try {
      if (initialMode === "signup") {
        const { error } = await signUp(email, password);
        if (error) {
          toast({
            title: "Kunde inte skapa konto",
            description: error.message,
            variant: "destructive",
          });
        } else {
          toast({
            title: "Konto skapat!",
            description: "Du är nu inloggad.",
          });
          onOpenChange(false);
          resetForm();
        }
      } else {
        const { error } = await signIn(email, password);
        if (error) {
          toast({
            title: "Kunde inte logga in",
            description: error.message,
            variant: "destructive",
          });
        } else {
          toast({
            title: "Inloggad!",
            description: "Välkommen tillbaka.",
          });
          onOpenChange(false);
          resetForm();
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setEmail("");
    setPassword("");
    setInternalMode(initialMode);
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      resetForm();
    }
    onOpenChange(newOpen);
  };

  const getTitle = () => {
    if (internalMode === "forgot") return "Glömt lösenord";
    return initialMode === "signup" ? "Skapa konto" : "Logga in";
  };

  const getSubmitText = () => {
    if (isSubmitting) return "Laddar...";
    if (internalMode === "forgot") return "Skicka återställningslänk";
    return initialMode === "signup" ? "Skapa konto" : "Logga in";
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-background border border-border max-w-md">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-foreground">
            {getTitle()}
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <div className="space-y-2">
            <Label htmlFor="email">E-post</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="din@email.se"
              required
            />
          </div>
          
          {internalMode !== "forgot" && (
            <div className="space-y-2">
              <Label htmlFor="password">Lösenord</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
          )}

          <Button
            type="submit"
            className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
            disabled={isSubmitting}
          >
            {getSubmitText()}
          </Button>
        </form>

        <div className="text-center mt-4 space-y-2">
          {internalMode === "forgot" ? (
            <p className="text-sm text-muted-foreground">
              <button
                type="button"
                onClick={() => setInternalMode("login")}
                className="text-primary hover:underline"
              >
                Tillbaka till inloggning
              </button>
            </p>
          ) : (
            <>
              {initialMode === "login" && (
                <p className="text-sm text-muted-foreground">
                  <button
                    type="button"
                    onClick={() => setInternalMode("forgot")}
                    className="text-primary hover:underline"
                  >
                    Glömt lösenord?
                  </button>
                </p>
              )}
              {initialMode === "signup" ? (
                <p className="text-sm text-muted-foreground">
                  Har du redan ett konto?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setInternalMode("login");
                      onModeChange("login");
                    }}
                    className="text-primary hover:underline"
                  >
                    Logga in
                  </button>
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Har du inget konto?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setInternalMode("signup");
                      onModeChange("signup");
                    }}
                    className="text-primary hover:underline"
                  >
                    Skapa konto
                  </button>
                </p>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AuthDialog;
