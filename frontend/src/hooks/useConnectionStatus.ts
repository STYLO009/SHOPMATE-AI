"use client";

/**
 * Connectivity status: browser online/offline events plus a lightweight
 * backend health ping so "Online" means the API actually answered.
 */

import { useEffect, useState } from "react";
import { system } from "@/lib/api";

export type ConnectionStatus = "online" | "offline" | "checking";

export function useConnectionStatus(): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>("checking");

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const ping = async () => {
      // Unit tests (jsdom) must never fire real network requests.
      if (process.env.NODE_ENV === "test") {
        if (alive) setStatus("online");
        return;
      }
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        if (alive) setStatus("offline");
        return;
      }
      try {
        await system.health();
        if (alive) setStatus("online");
      } catch {
        if (alive) setStatus("offline");
      } finally {
        if (alive) timer = setTimeout(ping, 45_000);
      }
    };

    const onOnline = () => setStatus("checking");
    const onOffline = () => setStatus("offline");

    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    void ping();

    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  return status;
}
