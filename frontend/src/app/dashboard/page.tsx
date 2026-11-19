"use client";

/**
 * Dashboard: gradient hero, colourful stat tiles, quick prompts,
 * category chips and recent conversations.
 */

import Link from "next/link";
import { useEffect, useState, type CSSProperties } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Bell,
  History,
  MessageSquare,
  Scale,
  Search,
  Sparkles,
  Tag,
  TrendingUp,
  Layers,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import AuthGuard from "@/components/AuthGuard";
import { useAuth } from "@/context/AuthContext";
import {
  conversations as conversationsApi,
  products as productsApi,
  watchlist as watchApi,
} from "@/lib/api";
import type { Conversation } from "@/lib/types";

const QUICK_PROMPTS = [
  {
    text: "Find me a laptop under ₹60000 for programming and gaming",
    hue: "from-blue-500/20 to-cyan-500/5",
    icon: "💻",
  },
  {
    text: "Compare the top wireless headphones under ₹3000",
    hue: "from-violet-500/20 to-fuchsia-500/5",
    icon: "🎧",
  },
  {
    text: "Which smartphone has the best camera around ₹45000?",
    hue: "from-emerald-500/20 to-teal-500/5",
    icon: "📱",
  },
  {
    text: "Analyze customer complaints about the Galaxy S24",
    hue: "from-amber-500/20 to-orange-500/5",
    icon: "🔍",
  },
];

const CATEGORY_ICONS: Record<string, string> = {
  laptop: "💻",
  smartphone: "📱",
  headphones: "🎧",
  smartwatch: "⌚",
  tablet: "📋",
  camera: "📷",
};

function DashboardInner() {
  const { user } = useAuth();
  const [recent, setRecent] = useState<Conversation[]>([]);
  const [categories, setCategories] = useState<{ category: string; count: number }[]>([]);
  const [savedCount, setSavedCount] = useState(0);

  useEffect(() => {
    conversationsApi
      .list()
      .then((c) => setRecent(c.slice(0, 5)))
      .catch(() => setRecent([]));
    productsApi
      .suggestions()
      .then((r) => setCategories(r.categories))
      .catch(() => setCategories([]));
    watchApi
      .savedList()
      .then((s) => setSavedCount(s.length))
      .catch(() => setSavedCount(0));
  }, []);

  const stats = [
    {
      label: "Conversations",
      value: recent.length,
      icon: MessageSquare,
      hue: "from-indigo-500/25 to-blue-500/10",
      iconColor: "text-indigo-400",
      href: "/history",
    },
    {
      label: "Categories",
      value: categories.length,
      icon: Layers,
      hue: "from-cyan-500/25 to-teal-500/10",
      iconColor: "text-cyan-400",
      href: "/explore",
    },
    {
      label: "Saved items",
      value: savedCount,
      icon: Sparkles,
      hue: "from-violet-500/25 to-purple-500/10",
      iconColor: "text-violet-400",
      href: "/saved",
    },
    {
      label: "Watchlist",
      value: "—",
      icon: Bell,
      hue: "from-amber-500/25 to-orange-500/10",
      iconColor: "text-amber-400",
      href: "/watchlist",
    },
  ];

  return (
    <>
      <Navbar />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10">
        {/* Gradient hero card */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-indigo-600/90 via-violet-600/80 to-cyan-600/70 p-7 text-white shadow-xl shadow-indigo-900/20"
        >
          <div
            className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl"
            aria-hidden
          />
          <div
            className="absolute -bottom-20 left-1/3 h-56 w-56 rounded-full bg-cyan-300/15 blur-2xl"
            aria-hidden
          />
          <div className="relative flex flex-wrap items-end justify-between gap-4">
            <div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-medium backdrop-blur">
                <Sparkles size={12} /> Agentic shopping workspace
              </span>
              <h1 className="mt-3 text-3xl font-bold">
                Welcome back{user ? `, ${user.full_name.split(" ")[0]}` : ""}
                👋
              </h1>
              <p className="mt-1 max-w-xl text-sm text-white/80">
                Start a question, explore categories, or jump back into a
                conversation — the research graph remembers your budget and
                preferences across turns.
              </p>
            </div>
            <div className="flex gap-2">
              <Link
                href="/explore"
                className="flex items-center gap-1.5 rounded-xl bg-white/15 px-4 py-2.5 text-sm font-semibold backdrop-blur transition hover:bg-white/25"
              >
                <TrendingUp size={15} /> Explore
              </Link>
              <Link
                href="/compare"
                className="flex items-center gap-1.5 rounded-xl bg-white/15 px-4 py-2.5 text-sm font-semibold backdrop-blur transition hover:bg-white/25"
              >
                <Scale size={15} /> Compare
              </Link>
              <Link
                href="/chat"
                className="flex items-center gap-1.5 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-indigo-700 transition hover:bg-white/90"
              >
                <MessageSquare size={15} /> New research
              </Link>
            </div>
          </div>
        </motion.div>

        {/* Stat tiles */}
        <section className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {stats.map(({ label, value, icon: Icon, hue, iconColor, href }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i }}
            >
              <Link
                href={href}
                className={`card group relative block overflow-hidden p-5 transition hover:-translate-y-1 hover:shadow-lg`}
              >
                <div
                  className={`absolute inset-x-0 top-0 h-16 bg-gradient-to-b ${hue}`}
                  aria-hidden
                />
                <div className="relative flex items-center justify-between">
                  <span className={`rounded-xl bg-surface/80 p-2.5 ${iconColor}`}>
                    <Icon size={20} />
                  </span>
                  <ArrowRight
                    size={15}
                    className="text-muted transition group-hover:translate-x-0.5 group-hover:text-accent"
                  />
                </div>
                <div className="relative mt-3 text-2xl font-black">{value}</div>
                <div className="relative text-xs text-muted">{label}</div>
              </Link>
            </motion.div>
          ))}
        </section>

        {/* Quick prompts */}
        <section className="mt-9">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted">
            <Sparkles size={14} className="text-accent-2" /> Ask anything
          </h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {QUICK_PROMPTS.map((prompt, i) => (
              <motion.div
                key={prompt.text}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
              >
                <Link
                  href={`/chat?q=${encodeURIComponent(prompt.text)}`}
                  className={`card group flex h-full items-center justify-between gap-3 bg-gradient-to-br ${prompt.hue} p-4 text-sm transition hover:border-accent`}
                >
                  <span className="flex items-center gap-3">
                    <span className="text-xl" aria-hidden>
                      {prompt.icon}
                    </span>
                    <span className="text-muted group-hover:text-foreground">
                      {prompt.text}
                    </span>
                  </span>
                  <ArrowRight size={15} className="shrink-0 text-accent" />
                </Link>
              </motion.div>
            ))}
          </div>
        </section>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          {/* Categories */}
          <section className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Categories in the catalogue</h2>
              <Link href="/explore" className="text-sm text-accent hover:underline">
                Browse all
              </Link>
            </div>
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
                  className="nav-pill capitalize"
                  style={
                    {
                      "--nav-hue":
                        category === "laptop"
                          ? "#4f8cff"
                          : category === "smartphone"
                            ? "#22d3ee"
                            : category === "headphones"
                              ? "#a78bfa"
                              : category === "smartwatch"
                                ? "#34d399"
                                : category === "tablet"
                                  ? "#fbbf24"
                                  : "#f472b6",
                    } as CSSProperties
                  }
                >
                  <span aria-hidden>{CATEGORY_ICONS[category] ?? "📦"}</span>
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
                <li className="text-sm text-muted">
                  No conversations yet — ask the agent anything to begin.
                </li>
              )}
              {recent.map((c, i) => (
                <li key={c.id}>
                  <Link
                    href={`/chat?c=${c.id}`}
                    className="flex items-center justify-between rounded-lg border border-border px-3 py-2.5 text-sm transition hover:border-accent"
                    style={
                      { borderLeftColor: ["#4f8cff", "#22d3ee", "#a78bfa", "#34d399", "#fbbf24"][i % 5] } as CSSProperties
                    }
                  >
                    <span className="truncate">{c.title}</span>
                    <span className="ml-3 flex shrink-0 items-center gap-1 text-xs text-muted">
                      <History size={12} /> {c.message_count}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex gap-2">
              <Link
                href="/chat"
                className="btn-primary flex flex-1 items-center justify-center gap-2 text-sm"
              >
                <MessageSquare size={15} /> New research
              </Link>
              <Link
                href="/deals"
                className="btn-ghost flex items-center gap-1.5 text-sm"
              >
                <Tag size={15} /> Deals
              </Link>
              <Link
                href="/explore"
                className="btn-ghost flex items-center gap-1.5 text-sm"
              >
                <Search size={15} /> Search
              </Link>
            </div>
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
