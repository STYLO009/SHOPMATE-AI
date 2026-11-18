"use client";

import { useCallback, useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import AuthGuard from "@/components/AuthGuard";
import ProductCard from "@/components/ProductCard";
import { watchlist as watchApi, ApiRequestError } from "@/lib/api";
import type { WatchlistEntry } from "@/lib/types";

function WatchlistInner() {
  const [items, setItems] = useState<WatchlistEntry[]>([]); const [targets, setTargets] = useState<Record<string, string>>({});
  const [message, setMessage] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(() => watchApi.list().then((rows) => { setItems(rows); setTargets(Object.fromEntries(rows.map((r) => [r.product.product_id, r.target_price == null ? "" : String(r.target_price)]))); }).catch((e: unknown) => setError(e instanceof ApiRequestError ? e.message : "Could not load the watchlist.")), []);
  useEffect(() => { void load(); }, [load]);
  const updateTarget = async (item: WatchlistEntry) => { setBusy(true); setError(""); try { await watchApi.add(item.product.product_id, targets[item.product.product_id] ? Number(targets[item.product.product_id]) : null); setMessage("Target price saved."); await load(); } catch (e) { setError(e instanceof ApiRequestError ? e.message : "Could not update target."); } finally { setBusy(false); } };
  const refresh = async () => { setBusy(true); setError(""); try { const result = await watchApi.refresh(); setMessage(`Checked ${result.checked} item${result.checked === 1 ? "" : "s"}.`); await load(); } catch (e) { setError(e instanceof ApiRequestError ? e.message : "Price refresh failed."); } finally { setBusy(false); } };
  const remove = async (id: string) => { try { await watchApi.remove(id); setItems((all) => all.filter((x) => x.product.product_id !== id)); } catch (e) { setError(e instanceof ApiRequestError ? e.message : "Could not remove item."); } };
  return <><Navbar /><main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10"><div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-3xl font-bold">Price <span className="text-gradient">watchlist</span></h1><p className="mt-1 text-sm text-muted">Set a target and recheck prices with the configured provider.</p></div><button type="button" disabled={busy || items.length === 0} onClick={() => void refresh()} className="btn-primary">{busy ? "Checking…" : "Refresh prices"}</button></div>{error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}{message && <p role="status" className="mt-4 text-sm text-success">{message}</p>}{items.length ? <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{items.map((item) => <section key={item.id} className="card p-4"><ProductCard product={item.product} /><div className="mt-3 flex items-end gap-2"><label className="flex-1 text-xs text-muted">Target price (₹)<input className="input mt-1" type="number" min="0" value={targets[item.product.product_id] ?? ""} onChange={(e) => setTargets((all) => ({ ...all, [item.product.product_id]: e.target.value }))} /></label><button className="btn-ghost text-sm" disabled={busy} onClick={() => void updateTarget(item)}>Save</button><button className="btn-ghost text-sm" onClick={() => void remove(item.product.product_id)}>Remove</button></div><p className="mt-2 text-xs text-muted">Last checked: {item.last_checked_at ? new Date(item.last_checked_at).toLocaleString() : "Not checked yet"} · {item.check_count} checks</p></section>)}</div> : <p className="card mt-6 p-6 text-sm text-muted">Your watchlist is empty. Add an item from product search.</p>}</main></>;
}
export default function WatchlistPage() { return <AuthGuard><WatchlistInner /></AuthGuard>; }
