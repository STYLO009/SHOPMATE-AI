"use client";

/** Dashboard: quick prompts, categories, recent conversations. */

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Bell,
  History,
  MessageSquare,
  Scale,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import AuthGuard from "@/components/AuthGuard";
import { conversations as conversationsApi, products as productsApi } from "@/lib/api";
import type { Conversation } from "@/lib/types";

const QUICK_PROMPTS = [
  "Find me a laptop under ₹60000 for programming and gaming",
  "Compare the top wireless headphones under ₹3000",
  "Which smartphone has the best camera around ₹45000?",
  "Analyze customer complaints about the Galaxy S24",
];

function DashboardInner() {
  const [recent, setRecent] = useState<Conversation[]>([]);
  const [categories, setCategories] = useState<{ category: string; count: number }[]>([]);

  useEffect(() => {
    conversationsApi
      .list()
      .then((c) => setRecent(c.slice(0, 5)))
      .catch(() => setRecent([]));
    productsApi
      .suggestions()
      .then((r) => setCategories(r.categories))
      .catch(() => setCategories([]));
  }, []);

  return (
    <>
      <Navbar />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-wrap items-end justify-between gap-4"
        >
          <div>
            <h1 className="text-3xl font-bold">
              Research <span className="text-gradient">dashboard</span>
            </h1>
            <p className="mt-1 text-sm text-muted">
              Start a question, explore categories, or jump back into a conversation.
            </p>
          </div>
          <div className="flex gap-2">
            <Link href="/explore" className="btn-ghost flex items-center gap-1.5 text-sm">
              <TrendingUp size={15} /> Explore
            </Link>
            <Link href="/compare" className="btn-ghost flex items-center gap-1.5 text-sm">
              <Scale size={15} /> Compare
            </Link>
            <Link href="/watchlist" className="btn-ghost flex items-center gap-1.5 text-sm">
              <Bell size={15} /> Watchlist
            </Link>
          </div>
        </motion.div>

        {/* Quick prompts */}
        <section className="mt-9">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted">
            <Sparkles size={14} className="text-accent-2" /> Ask anything
          </h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {QUICK_PROMPTS.map((prompt, i) => (
              <motion.div
                key={prompt}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
              >
                <Link
                  href={`/chat?q=${encodeURIComponent(prompt)}`}
                  className="card group flex h-full items-center justify-between gap-3 p-4 text-sm transition hover:border-accent"
                >
                  <span className="text-muted group-hover:text-foreground">{prompt}</span>
                  <ArrowRight size={15} className="shrink-0 text-accent" />
                </Link>
              </motion.div>
            ))}
          </div>
        </section>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          {/* Categories */}
          <section className="card p-5">
            <h2 className="font-semibold">Categories in the catalogue</h2>
            <p className="mt-1 text-xs text-muted">
              Derived from stored products (sample dataset unless a merchant API is connected).
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {categories.length === 0 && (
                <span className="text-sm text-muted">
                  No products indexed yet — run a search first.
                </span>
              )}
              {categories.map(({ category, count }) => (
                <Link
                  key={category}
                  href={`/explore?category=${encodeURIComponent(category)}`}
                  className="badge hover:border-accent hover:text-accent"
                >
                  {category} · {count}
                </Link>
              ))}
            </div>
          </section>

          {/* Recent conversations */}
          <section className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Recent research</h2>
              <Link href="/history" className="text-sm text-accent hover:underline">
                View all
              </Link>
            </div>
            <ul className="mt-3 flex flex-col gap-2">
              {recent.length === 0 && (
                <li className="text-sm text-muted">No conversations yet.</li>
              )}
              {recent.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/chat?c=${c.id}`}
                    className="flex items-center justify-between rounded-lg border border-border px-3 py-2.5 text-sm transition hover:border-accent"
                  >
                    <span className="truncate">{c.title}</span>
                    <span className="ml-3 flex shrink-0 items-center gap-1 text-xs text-muted">
                      <History size={12} /> {c.message_count}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <Link
              href="/chat"
              className="btn-primary mt-4 flex items-center justify-center gap-2 text-sm"
            >
              <MessageSquare size={15} /> New research
            </Link>
          </section>
        </div>
      </main>
    </>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardInner />
    </AuthGuard>
  );
}
