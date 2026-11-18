"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import AuthGuard from "@/components/AuthGuard";
import { conversations as conversationsApi, ApiRequestError } from "@/lib/api";
import type { Conversation } from "@/lib/types";

function HistoryInner() {
  const [items, setItems] = useState<Conversation[]>([]); const [error, setError] = useState("");
  const load = useCallback(() => conversationsApi.list().then(setItems).catch((e: unknown) => setError(e instanceof ApiRequestError ? e.message : "Could not load history.")), []);
  useEffect(() => { void load(); }, [load]);
  const remove = async (id: string) => { try { await conversationsApi.remove(id); setItems((all) => all.filter((item) => item.id !== id)); } catch (e) { setError(e instanceof ApiRequestError ? e.message : "Could not delete conversation."); } };
  return <><Navbar /><main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10"><h1 className="text-3xl font-bold">Research <span className="text-gradient">history</span></h1><p className="mt-1 text-sm text-muted">Return to a past conversation or remove it from your account.</p>{error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}<ul className="mt-6 flex flex-col gap-3">{items.map((item) => <li key={item.id} className="card flex items-center justify-between gap-4 p-4"><Link href={`/chat?c=${encodeURIComponent(item.id)}`} className="min-w-0 flex-1"><span className="block truncate font-medium">{item.title}</span><span className="mt-1 block text-xs text-muted">{item.message_count} messages · {new Date(item.updated_at).toLocaleString()}</span></Link><button type="button" onClick={() => void remove(item.id)} className="btn-ghost text-sm">Delete</button></li>)}</ul>{items.length === 0 && <p className="card mt-6 p-6 text-sm text-muted">No research conversations yet.</p>}</main></>;
}
export default function HistoryPage() { return <AuthGuard><HistoryInner /></AuthGuard>; }
