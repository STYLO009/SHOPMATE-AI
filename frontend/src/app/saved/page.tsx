"use client";

import { useCallback, useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import AuthGuard from "@/components/AuthGuard";
import ProductCard from "@/components/ProductCard";
import { watchlist as savedApi, ApiRequestError } from "@/lib/api";
import type { SavedProduct } from "@/lib/types";

function SavedInner() {
  const [items, setItems] = useState<SavedProduct[]>([]); const [error, setError] = useState("");
  const load = useCallback(() => savedApi.savedList().then(setItems).catch((e: unknown) => setError(e instanceof ApiRequestError ? e.message : "Could not load saved products.")), []);
  useEffect(() => { void load(); }, [load]);
  const remove = async (id: string) => { try { await savedApi.unsave(id); setItems((all) => all.filter((x) => x.product.product_id !== id)); } catch (e) { setError(e instanceof ApiRequestError ? e.message : "Could not remove product."); } };
  return <><Navbar /><main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10"><h1 className="text-3xl font-bold">Saved <span className="text-gradient">products</span></h1><p className="mt-1 text-sm text-muted">Products you’ve bookmarked for later.</p>{error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}{items.length ? <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{items.map((entry) => <ProductCard key={entry.id} product={entry.product} onSave={() => void remove(entry.product.product_id)} saved />)}</div> : <p className="card mt-6 p-6 text-sm text-muted">No saved products yet. Save one from Explore.</p>}</main></>;
}
export default function SavedPage() { return <AuthGuard><SavedInner /></AuthGuard>; }
