"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Scale,
  Search,
  Tag,
  Settings,
  Sparkles,
  X,
  Bookmark,
  Bell,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";

const LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Research", icon: MessageSquare },
  { href: "/explore", label: "Explore", icon: Search },
  { href: "/deals", label: "Live deals", icon: Tag },
  { href: "/compare", label: "Compare", icon: Scale },
  { href: "/saved", label: "Saved", icon: Bookmark },
  { href: "/watchlist", label: "Watchlist", icon: Bell },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

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
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-bold">
          <Sparkles size={20} className="text-accent-2" />
          <span className="text-gradient text-lg">ShopMate AI</span>
        </Link>

        <nav className="hidden items-center gap-1 lg:flex" data-testid="desktop-nav">
          {LINKS.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-accent/15 text-accent"
                    : "text-muted hover:bg-surface-2 hover:text-foreground"
                }`}
              >
                <Icon size={15} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <>
              <span className="hidden text-sm text-muted sm:block" data-testid="user-email">
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
            className="rounded-lg border border-border p-2 lg:hidden"
            data-testid="menu-toggle"
          >
            {open ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-border px-4 py-3 lg:hidden" data-testid="mobile-nav">
          <div className="grid grid-cols-2 gap-2">
            {LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                  pathname.startsWith(href) ? "bg-accent/15 text-accent" : "text-muted"
                }`}
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
