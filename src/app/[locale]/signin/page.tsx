"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { signIn } from "next-auth/react";

export default function SignInPage() {
  const t = useTranslations("auth");
  const common = useTranslations("common");
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });
    setBusy(false);
    if (result?.error) {
      setError(t("invalidCredentials"));
      return;
    }
    router.push(`/${params.locale}/admin`);
    router.refresh();
  };

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <h1>{t("title")}</h1>
        <p className="muted">{t("subtitle")}</p>
        <form onSubmit={submit}>
          <div>
            <label htmlFor="email">{common("email")}</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <label htmlFor="password">{common("password")}</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
          <button type="submit" disabled={busy}>
            {busy ? common("loading") : common("signIn")}
          </button>
        </form>
      </div>
    </div>
  );
}
