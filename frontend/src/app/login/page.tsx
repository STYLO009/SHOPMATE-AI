"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { motion } from "framer-motion";
import { KeyRound, Mail } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { auth as authApi, ApiRequestError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Sign in failed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const forgot = async () => {
    if (!email) {
      setError("Enter your email first, then request a reset link.");
      return;
    }
    try {
      await authApi.forgotPassword(email);
      setResetSent(true);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Request failed.");
    }
  };

  return (
    <main className="bg-grid flex flex-1 items-center justify-center px-4 py-16">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="card w-full max-w-md p-7"
      >
        <h1 className="text-2xl font-bold">Welcome back</h1>
        <p className="mt-1 text-sm text-muted">
          Sign in to continue your shopping research.
        </p>

        <form onSubmit={submit} className="mt-6 flex flex-col gap-4" data-testid="login-form">
          <label className="block">
            <span className="mb-1.5 block text-sm text-muted">Email</span>
            <div className="relative">
              <Mail size={15} className="absolute left-3 top-3 text-muted" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input pl-9"
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm text-muted">Password</span>
            <div className="relative">
              <KeyRound size={15} className="absolute left-3 top-3 text-muted" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input pl-9"
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
          </label>

          {error && (
            <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
              {error}
            </p>
          )}
          {resetSent && (
            <p className="rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm text-success" role="status">
              If an account exists for that email, a reset link has been sent.
            </p>
          )}

          <button type="submit" disabled={busy} className="btn-primary" data-testid="login-submit">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-4 flex items-center justify-between text-sm">
          <button type="button" onClick={forgot} className="text-muted underline hover:text-foreground">
            Forgot password?
          </button>
          <Link href="/signup" className="text-accent hover:underline">
            Create account
          </Link>
        </div>

        <div className="mt-5 border-t border-border pt-4 text-center text-sm text-muted">
          or
          <a
            href={authApi.googleLoginUrl()}
            className="btn-ghost mt-3 block"
            data-testid="google-login"
          >
            Continue with Google
          </a>
        </div>
      </motion.div>
    </main>
  );
}
