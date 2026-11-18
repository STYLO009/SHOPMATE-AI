"use client";

import Link from "next/link";
import Navbar from "@/components/Navbar";
import AuthGuard from "@/components/AuthGuard";
import { useAuth } from "@/context/AuthContext";

function SettingsInner() {
  const { user, refresh, logout } = useAuth();
  return <><Navbar /><main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10"><h1 className="text-3xl font-bold">Account <span className="text-gradient">settings</span></h1><p className="mt-1 text-sm text-muted">Manage your sign in and review the account details ShopMate stores.</p><section className="card mt-6 p-5"><h2 className="font-semibold">Profile</h2><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-muted">Name</dt><dd>{user?.full_name}</dd></div><div><dt className="text-muted">Email</dt><dd>{user?.email}</dd></div><div><dt className="text-muted">Sign in method</dt><dd>{user?.auth_provider === "google" ? "Google" : "Email and password"}</dd></div><div><dt className="text-muted">Email verified</dt><dd>{user?.email_verified ? "Yes" : "No"}</dd></div></dl><div className="mt-5 flex flex-wrap gap-2"><button className="btn-ghost" onClick={() => void refresh()}>Refresh profile</button><Link href="/login" className="btn-ghost">Change password</Link><button className="btn-ghost" onClick={() => void logout()}>Sign out</button></div></section><p className="mt-4 text-xs text-muted">Profile editing and account deletion are not currently available.</p></main></>;
}
export default function SettingsPage() { return <AuthGuard><SettingsInner /></AuthGuard>; }
