"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { login, AuthError } from "@/lib/auth";
import { PasswordChangePanel } from "@/components/auth/password-change-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPasswordChange, setShowPasswordChange] = useState(false);

  // Warn if accessed over non-HTTPS in production
  useEffect(() => {
    if (
      globalThis.window?.location.protocol === "http:" &&
      globalThis.window.location.hostname !== "localhost"
    ) {
      console.warn(
        "[internalCMDB] Login page loaded over HTTP. Credentials will be transmitted insecurely."
      );
    }
  }, []);

  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await login(email, password);
      if (result.force_password_change) {
        setShowPasswordChange(true);
      } else {
        navigateAfterLogin();
      }
    } catch (err) {
      if (err instanceof AuthError) {
        if (err.status === 429) {
          setError("Too many failed attempts. Try again in 15 minutes.");
        } else if (err.status === 401) {
          setError("Invalid email or password.");
        } else {
          setError(`Login failed (${err.status}). Please try again.`);
        }
      } else {
        setError("Network error. Please check your connection.");
      }
    } finally {
      setLoading(false);
    }
  }

  function navigateAfterLogin() {
    const from = searchParams.get("from");
    // Only allow same-origin relative paths (no open redirect)
    const destination =
      from && from.startsWith("/") && !from.startsWith("//") ? from : "/";
    router.replace(destination);
  }

  return (
    <>
      <Card
        style={{
          width: "100%",
          maxWidth: 420,
          margin: "0 auto",
        }}
      >
        <CardHeader>
          <CardTitle
            style={{
              fontSize: "1.4rem",
              fontFamily: "var(--font-bricolage)",
            }}
          >
            internalCMDB
          </CardTitle>
          <p style={{ fontSize: "0.9rem", opacity: 0.6, marginTop: 4 }}>
            Sign in to your account
          </p>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading}
              />
            </div>

            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={loading}
              aria-busy={loading}
            >
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <PasswordChangePanel
        required
        open={showPasswordChange}
        onSuccess={() => {
          setShowPasswordChange(false);
          navigateAfterLogin();
        }}
      />
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
