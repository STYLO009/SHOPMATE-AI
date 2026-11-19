"use client";

/**
 * Day/night theme context.
 *
 * The active theme lives on `<html data-theme="light|dark">` and is read
 * from localStorage by a tiny pre-hydration script (see layout.tsx) so the
 * first paint already matches — no flash of the wrong theme. This context
 * mirrors that attribute for React via `useSyncExternalStore` (DOM attribute
 * = external system; a custom event notifies React of programmatic changes).
 *
 * The context ships with a working fallback value so components (Navbar)
 * still behave sanely when rendered outside the provider — e.g. in unit
 * tests that mount a single page.
 */

import {
  createContext,
  useCallback,
  useContext,
  useSyncExternalStore,
  type ReactNode,
} from "react";

export type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const THEME_EVENT = "shopmate-theme-change";

function readDomTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(THEME_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(THEME_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function applyTheme(next: Theme) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem("shopmate-theme", next);
  } catch {
    /* storage blocked — theme still applies for this session */
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

/** Works even without a provider (unit tests render pages standalone). */
const fallbackTheme: ThemeContextValue = {
  theme: "dark",
  setTheme: applyTheme,
  toggleTheme: () => applyTheme(readDomTheme() === "light" ? "dark" : "light"),
};

const ThemeContext = createContext<ThemeContextValue>(fallbackTheme);

export function ThemeProvider({ children }: { children: ReactNode }) {
  // The pre-hydration script has already set the attribute before React
  // hydrates, so the client snapshot matches the server on first paint.
  const theme = useSyncExternalStore<Theme>(subscribe, readDomTheme, () => "dark");

  const setTheme = useCallback((next: Theme) => {
    applyTheme(next);
  }, []);

  const toggleTheme = useCallback(() => {
    applyTheme(readDomTheme() === "light" ? "dark" : "light");
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
