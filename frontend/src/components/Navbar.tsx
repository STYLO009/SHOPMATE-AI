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
 * App-shell navigation: a fixed left sidebar on large screens (one hue per
 * section pill, Settings pinned to the bottom-left) and a hamburger drawer
 * on small screens. Body gets `padding-left` on lg+ (see globals.css) so
 * page content and the footer shift right of the sidebar.
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
];

const RIBBON =
  "linear-gradient(90deg, #4f8cff, #22d3ee, #a78bfa, #f472b6, #fbbf24, #34d399)";

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
      className={`inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium ${color}`}
      data-testid="connection-status"
      data-status={status}
      title={
        status === "online"
          ? "Backend reachable"
          : status === "offline"
            ? "No connection to the backend"
            : "Checking backend…"
      }
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

function Brand() {
  return (
    <Link href="/" className="flex shrink-0 items-center gap-2 font-bold">
      <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent-2 text-[#04101f]">
        <Sparkles size={17} />
      </span>
      <span className="text-gradient text-lg">ShopMate AI</span>
    </Link>
  );
}

/** Vertical list of section pills (used by sidebar + mobile drawer). */
function NavPills({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <>
      {LINKS.map(({ href, label, icon: Icon, hue }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className="nav-pill"
            style={{ "--nav-hue": hue } as CSSProperties}
            data-active={active}
          >
            <Icon size={15} />
            <span className="nav-pill-dot h-1.5 w-1.5 rounded-full bg-transparent" />
            {label}
          </Link>
        );
      })}
    </>
  );
}

/** Status + theme + auth controls (sidebar / drawer bottom block). */
function ControlsBlock({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <StatusPill />
        <ThemeToggleButton />
      </div>

      {user ? (
        <div className="flex flex-col gap-2">
          <span className="truncate text-sm text-muted" data-testid="user-email">
            {user.full_name}
          </span>
          <button
            type="button"
            onClick={handleLogout}
            className="btn-ghost flex items-center justify-center gap-1.5 text-sm"
            data-testid="logout-button"
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Link href="/login" onClick={onNavigate} className="btn-ghost block text-center text-sm">
            Sign in
          </Link>
          <Link href="/signup" onClick={onNavigate} className="btn-primary block text-center text-sm">
            Get started
          </Link>
        </div>
      )}

      {/* Settings — pinned to the bottom-left corner of the nav. */}
      <Link
        href="/settings"
        onClick={onNavigate}
        className="nav-pill mt-1 border-t border-border pt-3"
        style={{ "--nav-hue": "#94a3b8" } as CSSProperties}
        data-active={pathname.startsWith("/settings")}
        data-testid="nav-settings"
      >
        <Settings size={15} />
        <span className="nav-pill-dot h-1.5 w-1.5 rounded-full bg-transparent" />
        Settings
      </Link>
    </>
  );
}

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* ------------------------------------------------- desktop sidebar */}
      <aside
        className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col overflow-y-auto border-r border-border bg-surface/80 backdrop-blur-lg lg:flex"
        data-testid="sidebar"
      >
        <div className="h-1 w-full shrink-0" style={{ background: RIBBON }} aria-hidden />
        <div className="px-4 pb-3 pt-5">
          <Brand />
        </div>

        <nav
          aria-label="Primary"
          className="flex flex-1 flex-col gap-1 overflow-y-auto scroll-thin px-3 py-2"
          data-testid="desktop-nav"
        >
          <NavPills />
        </nav>

        <div className="flex shrink-0 flex-col gap-3 border-t border-border p-3">
          <ControlsBlock />
        </div>
      </aside>

      {/* --------------------------------------------------- mobile topbar */}
      <header className="sticky top-0 z-40 glass lg:hidden">
        <div className="h-1 w-full" style={{ background: RIBBON }} aria-hidden />
        <div className="flex h-14 items-center justify-between px-4">
          <Brand />
          <div className="flex items-center gap-2">
            <ThemeToggleButton />
            <button
              type="button"
              aria-label="Toggle menu"
              onClick={() => setOpen((v) => !v)}
              className="rounded-lg border border-border p-2"
              data-testid="menu-toggle"
            >
              <Menu size={16} />
            </button>
          </div>
        </div>
      </header>

      {/* --------------------------------------------------- mobile drawer */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <nav
            aria-label="Primary mobile"
            className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-border bg-surface lg:hidden"
            data-testid="mobile-nav"
          >
            <div className="h-1 w-full shrink-0" style={{ background: RIBBON }} aria-hidden />
            <div className="flex items-center justify-between px-4 pb-3 pt-5">
              <Brand />
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="rounded-lg border border-border p-2 text-muted"
              >
                <X size={16} />
              </button>
            </div>

            <div className="flex flex-1 flex-col gap-1 overflow-y-auto scroll-thin px-3 py-2">
              <NavPills onNavigate={() => setOpen(false)} />
            </div>

            <div className="flex shrink-0 flex-col gap-3 border-t border-border p-3">
              <ControlsBlock onNavigate={() => setOpen(false)} />
            </div>
          </nav>
        </>
      )}
    </>
  );
}
