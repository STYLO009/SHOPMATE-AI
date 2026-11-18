"use client";

import { FormEvent, useState } from "react";
import Navbar from "@/components/Navbar";
import AuthGuard from "@/components/AuthGuard";
import ProductCard from "@/components/ProductCard";
import { products as productApi, ApiRequestError } from "@/lib/api";
import type { ComparisonResult, Product } from "@/lib/types";

function CompareInner() {
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const search = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(""); setComparison(null);
    try { setProducts((await productApi.search({ query, limit: 24 })).products); setSelected([]); }
    catch (e) { setError(e instanceof ApiRequestError ? e.message : "Product search failed."); }
    finally { setBusy(false); }
  };
  const toggle = (product: Product) => setSelected((ids) => ids.includes(product.id)
    ? ids.filter((id) => id !== product.id) : ids.length < 4 ? [...ids, product.id] : ids);
  const compare = async () => {
    setBusy(true); setError("");
    try { setComparison(await productApi.compare(selected)); }
    catch (e) { setError(e instanceof ApiRequestError ? e.message : "Comparison failed."); }
    finally { setBusy(false); }
  };
  return <><Navbar /><main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10">
    <h1 className="text-3xl font-bold">Product <span className="text-gradient">comparison</span></h1>
    <p className="mt-1 text-sm text-muted">Search the catalogue, choose two to four products, and compare known specifications.</p>
    <form onSubmit={search} className="mt-6 flex gap-2"><input className="input flex-1" required value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search laptops, phones, headphones…" aria-label="Search products" /><button className="btn-primary" disabled={busy}>Search</button></form>
    {error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}
    {products.length > 0 && <><div className="mt-5 flex items-center justify-between"><p className="text-sm text-muted">Select 2–4 products ({selected.length} selected)</p><button className="btn-primary" type="button" disabled={busy || selected.length < 2} onClick={() => void compare()}>{busy ? "Comparing…" : "Compare selected"}</button></div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{products.map((p) => <div key={p.id} className="relative"><ProductCard product={p} /><button type="button" onClick={() => toggle(p)} aria-pressed={selected.includes(p.id)} className={`btn-ghost mt-2 w-full ${selected.includes(p.id) ? "border-accent text-accent" : ""}`}>{selected.includes(p.id) ? "Selected" : "Add to comparison"}</button></div>)}</div></>}
    {comparison && <section className="card mt-8 overflow-x-auto p-5"><h2 className="text-xl font-semibold">Comparison results</h2>{comparison.verdict && <p className="mt-2 rounded-lg border border-accent/40 bg-accent/10 px-3 py-2 text-sm" data-testid="compare-verdict">{comparison.verdict}</p>}<p className="mt-2 text-sm text-muted">Price difference: {comparison.price_difference == null ? "—" : `₹${comparison.price_difference.toLocaleString("en-IN")}`}</p><table className="mt-4 w-full min-w-[600px] text-left text-sm"><thead><tr><th className="p-2">Specification</th>{comparison.products.map((p) => <th key={p.id} className="p-2">{p.title}{p.id === comparison.cheapest_product_id ? <span className="badge-sample ml-2">Cheapest</span> : null}{p.id === comparison.best_value_id ? <span className="badge ml-2 border-accent text-accent">Best value</span> : null}</th>)}</tr></thead><tbody>{comparison.spec_differences.map((diff) => <tr key={diff.spec} className="border-t border-border"><th className="p-2">{diff.spec.replaceAll("_", " ")}</th>{comparison.products.map((p) => <td key={p.id} className="p-2">{diff.values[p.id] ?? "Unknown"}{diff.better === p.id ? " · best" : ""}</td>)}</tr>)}</tbody></table>{comparison.missing_specs.length > 0 && <p className="mt-3 text-xs text-muted">Missing specifications: {comparison.missing_specs.join(", ")}</p>}{comparison.stale_products.length > 0 && <p className="mt-2 text-xs text-warning">Price data older than 24h for {comparison.stale_products.length} product(s) — verify at the retailer.</p>}</section>}
  </main></>;
}
export default function ComparePage() { return <AuthGuard><CompareInner /></AuthGuard>; }
