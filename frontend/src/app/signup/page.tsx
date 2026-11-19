"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import { ApiRequestError } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!terms) {
      setError("Please accept the terms to continue.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await register({ ...form, accept_terms: true });
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Registration failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Navbar />
      <main className="bg-grid flex flex-1 items-center justify-center px-4 py-16">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="card w-full max-w-md p-7"
        >
          <h1 className="text-2xl font-bold">Create your account</h1>
          <p className="mt-1 text-sm text-muted">
            Save conversations, watchlists and price alerts.
          </p>

          <form onSubmit={submit} className="mt-6 flex flex-col gap-4" data-testid="signup-form">
            <label className="block">
              <span className="mb-1.5 block text-sm text-muted">Full name</span>
              <input
                required
                minLength={2}
                value={form.full_name}
                onChange={set("full_name")}
                className="input"
                placeholder="Ada Lovelace"
                autoComplete="name"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm text-muted">Email</span>
              <input
                type="email"
                required
                value={form.email}
                onChange={set("email")}
                className="input"
                placeholder="you@example.com"
                autoComplete="email"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm text-muted">Password</span>
              <input
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={set("password")}
                className="input"
                placeholder="At least 8 characters"
                autoComplete="new-password"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm text-muted">Confirm password</span>
              <input
                type="password"
                required
                minLength={8}
                value={form.confirm_password}
                onChange={set("confirm_password")}
                className="input"
                placeholder="Repeat the password"
                autoComplete="new-password"
              />
            </label>

            <label className="flex items-start gap-2 text-sm text-muted">
              <input
                type="checkbox"
                checked={terms}
                onChange={(e) => setTerms(e.target.checked)}
                className="mt-1"
              />
              I agree to the terms of service and privacy policy.
            </label>

            {error && (
              <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
                {error}
              </p>
            )}

            <button type="submit" disabled={busy} className="btn-primary" data-testid="signup-submit">
              {busy ? "Creating account…" : "Create account"}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-muted">
            Already registered?{" "}
            <Link href="/login" className="text-accent hover:underline">
              Sign in
            </Link>
          </p>
        </motion.div>
      </main>
    </>
  );
}
