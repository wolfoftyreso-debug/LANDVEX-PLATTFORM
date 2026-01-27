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

interface AuthDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "login" | "signup";
  onModeChange: (mode: "login" | "signup") => void;
}

const AuthDialog = ({ open, onOpenChange, mode, onModeChange }: AuthDialogProps) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { signIn, signUp } = useAuth();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
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
      if (mode === "signup") {
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
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-background border border-border max-w-md">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-foreground">
            {mode === "signup" ? "Skapa konto" : "Logga in"}
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

          <Button
            type="submit"
            className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? "Laddar..."
              : mode === "signup"
              ? "Skapa konto"
              : "Logga in"}
          </Button>
        </form>

        <div className="text-center mt-4">
          {mode === "signup" ? (
            <p className="text-sm text-muted-foreground">
              Har du redan ett konto?{" "}
              <button
                type="button"
                onClick={() => onModeChange("login")}
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
                onClick={() => onModeChange("signup")}
                className="text-primary hover:underline"
              >
                Skapa konto
              </button>
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AuthDialog;
