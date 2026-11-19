"use client";

import Link from "next/link";
import { Suspense, FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import { ApiRequestError, auth as authApi } from "@/lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("This reset link is missing its token. Request a new link.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Password reset failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Navbar />
      <main className="bg-grid flex flex-1 items-center justify-center px-4 py-16">
        <motion.section initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }} className="card w-full max-w-md p-7">
          <h1 className="text-2xl font-bold">Set a new password</h1>
          <p className="mt-1 text-sm text-muted">Choose a new password for your account.</p>
          {done ? (
            <div className="mt-6">
              <p className="rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm text-success" role="status">
                Password updated. You can sign in with your new password.
              </p>
              <Link href="/login" className="btn-primary mt-5 block text-center">Go to sign in</Link>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
              <label className="block">
                <span className="mb-1.5 block text-sm text-muted">New password</span>
                <input type="password" required minLength={8} maxLength={128} autoComplete="new-password"
                  value={password} onChange={(event) => setPassword(event.target.value)} className="input" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm text-muted">Confirm new password</span>
                <input type="password" required minLength={8} maxLength={128} autoComplete="new-password"
                  value={confirm} onChange={(event) => setConfirm(event.target.value)} className="input" />
              </label>
              {error && <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">{error}</p>}
              <button type="submit" disabled={busy} className="btn-primary">
                {busy ? "Updating…" : "Update password"}
              </button>
            </form>
          )}
        </motion.section>
      </main>
    </>
  );
}

export default function ResetPasswordPage() {
  return <Suspense fallback={<main className="flex flex-1 items-center justify-center text-muted">Loading reset form…</main>}>
    <ResetPasswordForm />
  </Suspense>;
}
