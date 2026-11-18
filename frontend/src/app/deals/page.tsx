"use client";

import { FormEvent, useEffect, useState } from "react";
import { ExternalLink, Loader2, Search, Tag } from "lucide-react";
import Navbar from "@/components/Navbar";
import { ApiRequestError, offers as offersApi } from "@/lib/api";
import type { FeaturedOffer, RetailOffer } from "@/lib/types";

function money(value: number, currency: string) {
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString("en-IN")}`;
  }
}

function timestamp(value: string | null) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleString();
}

export default function DealsPage() {
  const [query, setQuery] = useState("");
  const [featured, setFeatured] = useState<FeaturedOffer[]>([]);
  const [deals, setDeals] = useState<RetailOffer[]>([]);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerErrors, setProviderErrors] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    offersApi.featured().then((response) => {
      if (!active) return;
      setFeatured(response.offers);
      setProviderErrors(response.provider_errors ?? []);
    }).catch((err: unknown) => {
      if (active) setError(err instanceof ApiRequestError ? err.message : "Could not load live offers.");
    });
    return () => { active = false; };
  }, []);

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    setSearched(true);
    try {
      const response = await offersApi.search(query.trim());
      setDeals(response.offers);
      setProviderErrors(response.provider_errors ?? []);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Could not search live offers.");
      setDeals([]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Navbar />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10">
        <div className="flex items-center gap-3">
          <Tag className="text-accent-2" />
          <div>
            <h1 className="text-3xl font-bold">Live retailer offers</h1>
            <p className="mt-1 text-sm text-muted">Public offers from connected Amazon and Flipkart affiliate feeds.</p>
          </div>
        </div>

        <form onSubmit={search} className="mt-7 flex gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-3.5 text-muted" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} className="input pl-10" placeholder="Search offers, e.g. headphones" aria-label="Search offers" />
          </div>
          <button className="btn-primary flex min-w-28 items-center justify-center gap-2" disabled={busy || !query.trim()}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />} Search
          </button>
        </form>

        {error && <p role="alert" className="mt-4 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
        {providerErrors.length > 0 && <p className="mt-4 text-sm text-muted">Some feeds are unavailable: {providerErrors.join(" · ")}</p>}

        {searched && <section className="mt-9">
          <h2 className="mb-4 text-xl font-semibold">Search results</h2>
          {deals.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {deals.map((deal) => <DealCard key={`${deal.merchant}-${deal.product_id}`} deal={deal} />)}
          </div> : !busy && <p className="card p-6 text-sm text-muted">No current discounted offers found for that search.</p>}
        </section>}

        <section className="mt-10">
          <h2 className="mb-4 text-xl font-semibold">Featured deals of the day</h2>
          {featured.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((deal) => <article key={deal.id} className="card flex flex-col overflow-hidden">
              {/* Retailer CDNs are arbitrary hosts; keep plain img (no proxy). */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {deal.image_url && <img src={deal.image_url} alt="" className="h-44 w-full object-contain bg-white p-3" loading="lazy" />}
              <div className="flex flex-1 flex-col p-5">
                <p className="text-xs uppercase tracking-wide text-accent-2">{deal.merchant}{deal.category ? ` · ${deal.category}` : ""}</p>
                <h3 className="mt-2 font-semibold">{deal.title}</h3>
                {deal.description && <p className="mt-2 line-clamp-3 text-sm text-muted">{deal.description}</p>}
                <div className="mt-auto pt-4 text-xs text-muted">{deal.expires_at ? `Ends ${timestamp(deal.expires_at) ?? "soon"}` : "Check retailer for availability and end time"}</div>
                <a href={deal.url} target="_blank" rel="noopener noreferrer sponsored" className="btn-primary mt-3 inline-flex items-center justify-center gap-2">View offer <ExternalLink size={14} /></a>
              </div>
            </article>)}
          </div> : <p className="card p-6 text-sm text-muted">No featured feed is available right now. Live deals appear here when affiliate feeds are configured.</p>}
        </section>

        <p className="mt-10 border-t border-border pt-5 text-xs leading-relaxed text-muted">
          We may earn a commission from qualifying purchases. Prices and availability can change; retailer checkout is authoritative. Price details are shown with their last verified time.
        </p>
      </main>
    </>
  );
}

function DealCard({ deal }: { deal: RetailOffer }) {
  return <article className="card flex flex-col overflow-hidden">
    {/* Retailer CDNs are arbitrary hosts; keep plain img (no proxy). */}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    {deal.image_url && <img src={deal.image_url} alt="" className="h-44 w-full object-contain bg-white p-3" loading="lazy" />}
    <div className="flex flex-1 flex-col p-5">
      <p className="text-xs uppercase tracking-wide text-accent-2">{deal.merchant}{deal.category ? ` · ${deal.category}` : ""}</p>
      <h3 className="mt-2 font-semibold">{deal.title}</h3>
      {deal.deal_title && <p className="mt-2 text-sm text-muted">{deal.deal_title}</p>}
      <div className="mt-4 flex flex-wrap items-baseline gap-2">
        <span className="text-xl font-bold">{money(deal.price, deal.currency)}</span>
        {deal.original_price && deal.original_price > deal.price && <del className="text-sm text-muted">{money(deal.original_price, deal.currency)}</del>}
        {deal.discount_percentage != null && <span className="badge">{deal.discount_percentage}% off</span>}
      </div>
      <p className="mt-2 text-xs text-muted">Price verified {timestamp(deal.last_verified_at) ?? "recently"}{deal.expires_at ? ` · Offer ends ${timestamp(deal.expires_at) ?? "soon"}` : ""}</p>
      <a href={deal.product_url ?? undefined} target="_blank" rel="noopener noreferrer sponsored" className="btn-primary mt-auto inline-flex items-center justify-center gap-2 pt-3">View at {deal.merchant} <ExternalLink size={14} /></a>
    </div>
  </article>;
}
