"use client";

/** Route guard: redirects to /login when the backend says "not signed in". */

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-muted">
        Checking your session…
      </div>
    );
  }

  if (!user) return null;
  return <>{children}</>;
}
