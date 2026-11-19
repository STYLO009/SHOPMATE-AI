import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import Footer from "@/components/Footer";
import ChatDock from "@/components/ChatDock";

export const metadata: Metadata = {
  title: "ShopMate AI — Autonomous Shopping Intelligence",
  description:
    "Agentic AI research assistant that searches, compares and ranks products with explainable recommendations.",
};

/**
 * Applies the persisted theme before hydration so the first paint already
 * matches day/night mode (no flash). Kept tiny and dependency-free.
 */
const themeScript = `(function(){try{var t=localStorage.getItem("shopmate-theme");if(!t){t=window.matchMedia&&window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";}document.documentElement.dataset.theme=t;}catch(e){document.documentElement.dataset.theme="dark";}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="flex min-h-full flex-col">
        <ThemeProvider>
          <AuthProvider>
            {children}
            <Footer />
            <ChatDock />
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
