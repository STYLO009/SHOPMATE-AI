"use client";

/**
 * Explore: opens like a storefront — the featured catalogue feed loads
 * immediately (no empty state), with category chips and trending searches
 * on top of the real provider search, filters, sorting and sample-data
 * labelling.
 */

import { FormEvent, Suspense, useCallback, useEffect, useState, type CSSProperties } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Flame, Loader2, Search, SlidersHorizontal, Sparkles, X } from "lucide-react";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import ProductCard, { type AnyProduct } from "@/components/ProductCard";
import { products as productsApi, ApiRequestError, watchlist as watchApi } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";

const CATEGORIES = [
  "laptop",
  "smartphone",
  "headphones",
  "smartwatch",
  "tablet",
  "camera",
];

/** Colour per category chip — keeps the filter row lively, not grey. */
const CATEGORY_HUES: Record<string, string> = {
  laptop: "#4f8cff",
  smartphone: "#22d3ee",
  headphones: "#a78bfa",
  smartwatch: "#34d399",
  tablet: "#fbbf24",
  camera: "#f472b6",
};

const TRENDING = [
  "gaming laptop",
  "wireless headphones",
  "smartphone under 45000",
  "smartwatch",
  "mirrorless camera",
];

const SORTS = [
  { value: "relevance", label: "Relevance" },
  { value: "price_asc", label: "Price: low → high" },
  { value: "price_desc", label: "Price: high → low" },
  { value: "rating", label: "Rating" },
];

function ExploreInner() {
  const { user } = useAuth();
  const params = useSearchParams();
  const [query, setQuery] = useState(() => params.get("q") ?? "");
  const [category, setCategory] = useState<string>(params.get("category") ?? "");
  const [budgetMax, setBudgetMax] = useState("");
  const [sortBy, setSortBy] = useState("relevance");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [mode, setMode] = useState<"featured" | "search">("featured");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

  const search = useCallback(
    async (q: string, cat: string, budget: string, sort: string) => {
      setBusy(true);
      setError(null);
      try {
        const effectiveQuery = q.trim() || cat.trim();
        if (!effectiveQuery) {
          // Nothing to search: fall back to the featured feed.
          const feed = await productsApi.featured({ category: cat || null, limit: 24 });
          setResult(feed);
          setMode("featured");
          return;
        }
        const res = await productsApi.search({
          query: effectiveQuery,
          category: cat || null,
          budget_max: budget ? Number(budget) : null,
          sort_by: sort,
          limit: 24,
        });
        setResult(res);
        setMode("search");
      } catch (err) {
        setError(
          err instanceof ApiRequestError ? err.message : "Search failed.",
        );
        setResult(null);
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  // Initial load: URL-driven search if present, otherwise the featured feed
  // so the page is populated the moment it opens (like a storefront).
  useEffect(() => {
    const q = params.get("q")?.trim() ?? "";
    const cat = params.get("category") ?? "";
    let cancelled = false;

    const load = async () => {
      setBusy(true);
      setError(null);
      try {
        if (q || cat.trim()) {
          const res = await productsApi.search({
            query: q || cat.trim(),
            category: cat || null,
            limit: 24,
            sort_by: "relevance",
          });
          if (!cancelled) {
            setResult(res);
            setMode("search");
          }
        } else {
          const feed = await productsApi.featured({ limit: 24 });
          if (!cancelled) {
            setResult(feed);
            setMode("featured");
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiRequestError ? err.message : "Search failed.");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void search(query, category, budgetMax, sortBy);
  };

  const pickCategory = (cat: string) => {
    const next = cat === category ? "" : cat;
    setCategory(next);
    void search(query, next, budgetMax, sortBy);
  };

  const runTrending = (term: string) => {
    setQuery(term);
    setCategory("");
    void search(term, "", budgetMax, sortBy);
  };

  const clearFilters = () => {
    setQuery("");
    setCategory("");
    setBudgetMax("");
    setSortBy("relevance");
    void search("", "", "", "relevance");
  };

  const toggleSave = async (p: AnyProduct) => {
    const id = "provider_product_id" in p ? p.provider_product_id : p.product_id;
    try {
      if (savedIds.has(id)) {
        await watchApi.unsave(id);
        setSavedIds((s) => {
          const n = new Set(s);
          n.delete(id);
          return n;
        });
      } else {
        await watchApi.save(id);
        setSavedIds((s) => new Set(s).add(id));
      }
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Could not update saved list.");
    }
  };

  const hasQuery = Boolean(query.trim() || category || budgetMax);

  return (
    <>
      <Navbar />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10">
        <h1 className="text-3xl font-bold">
          Explore the <span className="text-gradient">catalogue</span>
        </h1>
        <p className="mt-1 text-sm text-muted">
          Searches every configured provider, merges results and labels sample data.
        </p>

        {/* Category chips */}
        <div className="mt-5 flex flex-wrap items-center gap-2" role="list" aria-label="Categories">
          <button
            type="button"
            onClick={() => pickCategory("")}
            className="nav-pill border-border"
            style={{ "--nav-hue": "#94a3b8" } as CSSProperties}
            data-active={category === ""}
          >
            All
          </button>
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => pickCategory(c)}
              className="nav-pill capitalize"
              style={{ "--nav-hue": CATEGORY_HUES[c] } as CSSProperties}
              data-active={category === c}
            >
              {c}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-3 lg:flex-row">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-3.5 text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search products…"
              className="input pl-10"
              aria-label="Search query"
            />
          </div>

          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="input lg:w-48"
            aria-label="Category"
          >
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <input
            type="number"
            min={0}
            value={budgetMax}
            onChange={(e) => setBudgetMax(e.target.value)}
            placeholder="Max budget"
            className="input lg:w-40"
            aria-label="Maximum budget"
          />

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="input lg:w-52"
            aria-label="Sort by"
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>

          <button type="submit" disabled={busy} className="btn-primary flex items-center justify-center gap-2">
            {busy ? <Loader2 size={16} className="animate-spin" /> : <SlidersHorizontal size={16} />}
            Search
          </button>
        </form>

        {/* Trending searches — only when the user hasn't searched yet */}
        {mode === "featured" && !hasQuery && (
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <span className="flex items-center gap-1 font-semibold uppercase tracking-wide text-muted">
              <Flame size={13} className="text-warning" /> Trending
            </span>
            {TRENDING.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => runTrending(t)}
                className="badge transition hover:border-accent hover:text-accent"
              >
                {t}
              </button>
            ))}
          </div>
        )}

        {error && (
          <p className="mt-4 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
            {error}
          </p>
        )}

        {result && (
          <div className="mt-5 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="flex items-center gap-1 font-medium text-foreground">
              {mode === "featured" ? (
                <>
                  <Sparkles size={13} className="text-accent-2" /> Featured products
                </>
              ) : (
                <>
                  {result.total} result{result.total === 1 ? "" : "s"} in {result.took_ms}ms
                </>
              )}
            </span>
            <span className="badge">{result.providers_queried.join(", ")}</span>
            {result.is_sample_data && <span className="badge-sample">Sample data</span>}
            {result.provider_errors.map((e) => (
              <span key={e} className="badge border-warning/50 text-warning">
                {e}
              </span>
            ))}
            {hasQuery && (
              <button
                type="button"
                onClick={clearFilters}
                className="ml-auto inline-flex items-center gap-1 text-accent transition hover:underline"
              >
                <X size={12} /> Clear
              </button>
            )}
          </div>
        )}

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {result?.products.map((p, i) => (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.04, 0.4) }}
            >
              <ProductCard
                product={p}
                saved={savedIds.has(p.provider_product_id)}
                onSave={user ? toggleSave : undefined}
              />
            </motion.div>
          ))}
        </section>

        {busy && !result && (
          <div className="card mt-8 flex items-center justify-center gap-2 p-10 text-muted">
            <Loader2 size={18} className="animate-spin" /> Loading catalogue…
          </div>
        )}

        {result && result.products.length === 0 && !busy && (
          <div className="card mt-8 p-10 text-center">
            <p className="text-muted">No products matched.</p>
            <p className="mt-1 text-sm text-muted">
              Try a different query, clear the budget filter, or pick another category.
            </p>
            <button type="button" onClick={clearFilters} className="btn-ghost mt-4 inline-block text-sm">
              Reset filters
            </button>
          </div>
        )}
      </main>
    </>
  );
}

export default function ExplorePage() {
  return <Suspense fallback={<main className="mx-auto max-w-7xl px-4 py-10 text-sm text-muted">Loading catalogue…</main>}><ExploreInner /></Suspense>;
}
