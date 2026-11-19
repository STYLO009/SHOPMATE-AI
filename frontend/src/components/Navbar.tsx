"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  Scale,
  Search,
  Tag,
  Settings,
  Sparkles,
  Sun,
  WifiOff,
  Loader2,
  X,
  Bookmark,
  Bell,
} from "lucide-react";
import { useState, type CSSProperties } from "react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { useConnectionStatus } from "@/hooks/useConnectionStatus";

/**
 * Each section owns a hue: the pill shows a tinted background + a glowing
 * dot in that colour when active, so the bar reads as a colourful dashboard
 * rail instead of uniform grey links.
 */
const LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, hue: "#818cf8" },
  { href: "/chat", label: "Research", icon: MessageSquare, hue: "#22d3ee" },
  { href: "/explore", label: "Explore", icon: Search, hue: "#34d399" },
  { href: "/deals", label: "Live deals", icon: Tag, hue: "#fbbf24" },
  { href: "/compare", label: "Compare", icon: Scale, hue: "#f472b6" },
  { href: "/saved", label: "Saved", icon: Bookmark, hue: "#a78bfa" },
  { href: "/watchlist", label: "Watchlist", icon: Bell, hue: "#fb923c" },
  { href: "/history", label: "History", icon: History, hue: "#60a5fa" },
  { href: "/settings", label: "Settings", icon: Settings, hue: "#94a3b8" },
];

function StatusPill() {
  const status = useConnectionStatus();
  const label =
    status === "online" ? "Online" : status === "offline" ? "Offline" : "Checking…";
  const color =
    status === "online" ? "text-success" : status === "offline" ? "text-danger" : "text-muted";
  const dotBg =
    status === "online" ? "bg-success" : status === "offline" ? "bg-danger" : "bg-muted";
  return (
    <span
      className={`hidden items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium sm:inline-flex ${color}`}
      data-testid="connection-status"
      data-status={status}
      title={status === "online" ? "Backend reachable" : status === "offline" ? "No connection to the backend" : "Checking backend…"}
    >
      {status === "checking" ? (
        <Loader2 size={12} className="animate-spin" />
      ) : status === "offline" ? (
        <WifiOff size={12} />
      ) : (
        <span className={`status-dot ${dotBg} text-current`} />
      )}
      {label}
    </span>
  );
}

function ThemeToggleButton() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={theme === "light" ? "Switch to night mode" : "Switch to day mode"}
      data-testid="theme-toggle"
      className="rounded-full border border-border bg-surface p-2 text-muted transition hover:border-accent hover:text-accent"
    >
      {theme === "light" ? <Moon size={15} /> : <Sun size={15} />}
    </button>
  );
}

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header className="glass sticky top-0 z-40">
      {/* Colourful top ribbon */}
      <div
        className="h-1 w-full"
        style={{
          background:
            "linear-gradient(90deg, #4f8cff, #22d3ee, #a78bfa, #f472b6, #fbbf24, #34d399)",
        }}
        aria-hidden
      />
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-bold">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent-2 text-[#04101f]">
            <Sparkles size={17} />
          </span>
          <span className="text-gradient text-lg">ShopMate AI</span>
        </Link>

        <nav className="hidden items-center gap-1 xl:flex" data-testid="desktop-nav">
          {LINKS.map(({ href, label, icon: Icon, hue }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className="nav-pill"
                style={{ "--nav-hue": hue } as CSSProperties}
                data-active={active}
              >
                <Icon size={14} />
                <span className="nav-pill-dot h-1.5 w-1.5 rounded-full bg-transparent" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <StatusPill />
          <ThemeToggleButton />
          {user ? (
            <>
              <span className="hidden text-sm text-muted lg:block" data-testid="user-email">
                {user.full_name}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="btn-ghost flex items-center gap-1.5 text-sm"
                data-testid="logout-button"
              >
                <LogOut size={14} /> <span className="hidden sm:inline">Sign out</span>
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="btn-ghost text-sm">
                Sign in
              </Link>
              <Link href="/signup" className="btn-primary text-sm">
                Get started
              </Link>
            </>
          )}
          <button
            type="button"
            aria-label="Toggle menu"
            onClick={() => setOpen((v) => !v)}
            className="rounded-lg border border-border p-2 xl:hidden"
            data-testid="menu-toggle"
          >
            {open ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-border px-4 py-3 xl:hidden" data-testid="mobile-nav">
          <div className="grid grid-cols-2 gap-2">
            {LINKS.map(({ href, label, icon: Icon, hue }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className="nav-pill"
                style={{ "--nav-hue": hue } as CSSProperties}
                data-active={pathname.startsWith(href)}
              >
                <Icon size={15} /> {label}
              </Link>
            ))}
          </div>
        </nav>
      )}
    </header>
  );
}
