"use client";

/**
 * Site-wide footer: brand column, product/resources link columns and the
 * data-honesty disclaimer. Rendered by the root layout so every route
 * (landing, auth, dashboard…) gets a complete "real website" frame.
 */

import Link from "next/link";
import {
  ArrowUpRight,
  GitBranch,
  MessageSquare,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useConnectionStatus } from "@/hooks/useConnectionStatus";

const COLUMNS: { title: string; links: { label: string; href: string }[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Dashboard", href: "/dashboard" },
      { label: "Explore", href: "/explore" },
      { label: "Live deals", href: "/deals" },
      { label: "Compare", href: "/compare" },
    ],
  },
  {
    title: "Research",
    links: [
      { label: "Agentic chat", href: "/chat" },
      { label: "History", href: "/history" },
      { label: "Watchlist", href: "/watchlist" },
      { label: "Saved items", href: "/saved" },
    ],
  },
  {
    title: "Account",
    links: [
      { label: "Settings", href: "/settings" },
      { label: "Sign in", href: "/login" },
      { label: "Create account", href: "/signup" },
      { label: "Reset password", href: "/reset-password" },
    ],
  },
];

export default function Footer() {
  const status = useConnectionStatus();
  return (
    <footer className="border-t border-border bg-surface/50">
      <div
        className="h-1 w-full"
        style={{
          background:
            "linear-gradient(90deg, #34d399, #22d3ee, #4f8cff, #a78bfa, #f472b6, #fbbf24)",
        }}
        aria-hidden
      />
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 md:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <Link href="/" className="flex items-center gap-2 font-bold">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent-2 text-[#04101f]">
              <Sparkles size={17} />
            </span>
            <span className="text-gradient text-lg">ShopMate AI</span>
          </Link>
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted">
            Autonomous agentic shopping intelligence — a multi-agent LangGraph
            workflow that searches, compares and ranks products, then explains
            every recommendation factor by factor.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted">
            <span
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1"
              data-testid="footer-status"
            >
              <span
                className={`status-dot ${
                  status === "online"
                    ? "bg-success text-success"
                    : status === "offline"
                      ? "bg-danger text-danger"
                      : "bg-muted text-muted"
                }`}
              />
              {status === "online"
                ? "All systems online"
                : status === "offline"
                  ? "Backend unreachable"
                  : "Checking status…"}
            </span>
            <a
              href="https://github.com/STYLO009/SHOPMATE-AI"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 transition hover:text-accent"
            >
              <GitBranch size={13} /> Source <ArrowUpRight size={11} />
            </a>
          </div>
        </div>

        {COLUMNS.map((col) => (
          <nav key={col.title} aria-label={col.title}>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
              {col.title}
            </h3>
            <ul className="mt-3 flex flex-col gap-2">
              {col.links.map((l) => (
                <li key={l.href + l.label}>
                  <Link
                    href={l.href}
                    className="text-sm text-muted transition hover:text-accent"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>

      <div className="border-t border-border">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 px-4 py-5 text-xs text-muted sm:flex-row">
          <p>© 2026 ShopMate AI · demo platform</p>
          <p className="flex items-center gap-1.5 text-center sm:text-right">
            <ShieldCheck size={13} className="text-success" />
            Sample data is clearly labelled and never presented as live pricing.
          </p>
          <Link
            href="/chat"
            className="inline-flex items-center gap-1 transition hover:text-accent"
          >
            <MessageSquare size={13} /> Ask the research agent
          </Link>
        </div>
      </div>
    </footer>
  );
}
