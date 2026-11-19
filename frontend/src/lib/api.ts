/**
 * ShopMate API client.
 *
 * All requests use `credentials: "include"` so the httpOnly JWT cookie set by
 * the backend travels with every call — the frontend never sees or stores the
 * token itself.
 */

import type {
  AuthResponse,
  ChatResponse,
  ComparisonResult,
  Conversation,
  ConversationDetail,
  Product,
  FeaturedOffer,
  RetailOffer,
  RecommendationResponse,
  ReviewAnalysisResponse,
  SavedProduct,
  SearchResponse,
  User,
  WatchlistEntry,
} from "./types";

function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (typeof window === "undefined") return configured ?? "http://localhost:8000";

  const pageHost = window.location.hostname;
  const loopback = (host: string) => host === "localhost" || host === "127.0.0.1";
  if (configured) {
    try {
      const url = new URL(configured, window.location.origin);
      // localhost and 127.0.0.1 are separate cookie hosts. Align local API
      // configuration with the hostname through which the user opened the UI.
      if (loopback(url.hostname) && loopback(pageHost)) url.hostname = pageHost;
      return url.toString().replace(/\/$/, "");
    } catch {
      return configured;
    }
  }
  // Not configured: on localhost talk to the local API on :8000; anywhere
  // else (e.g. Vercel) use same-origin relative paths — the deployment
  // proxies /api/* to the backend (see rewrites in next.config.ts), which
  // keeps the httpOnly session cookie same-site.
  if (loopback(pageHost)) return `${window.location.protocol}//${pageHost}:8000`;
  return "";
}

export const API_BASE = resolveApiBase();

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal } = opts;
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!res.ok) {
    let code = "request_failed";
    let message = `Request failed (${res.status})`;
    try {
      const payload = await res.json();
      const detail = payload?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object") {
        code = detail.code ?? code;
        message = detail.message ?? message;
      } else if (payload?.message) {
        message = payload.message;
      }
    } catch {
      /* non-JSON error body — keep defaults */
    }
    throw new ApiRequestError(res.status, code, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ------------------------------------------------------------------ auth */

export const auth = {
  register: (data: {
    full_name: string;
    email: string;
    password: string;
    confirm_password: string;
    accept_terms: boolean;
  }) =>
    request<AuthResponse>("/api/auth/register", { method: "POST", body: data }),

  login: (data: { email: string; password: string; remember?: boolean }) =>
    request<AuthResponse>("/api/auth/login", { method: "POST", body: data }),

  logout: () => request<{ message: string }>("/api/auth/logout", { method: "POST" }),

  me: () => request<User>("/api/auth/me"),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/api/auth/forgot-password", {
      method: "POST",
      body: { email },
    }),

  resetPassword: (token: string, password: string) =>
    request<{ message: string }>("/api/auth/reset-password", {
      method: "POST",
      body: { token, password },
    }),

  /** Full URL of the backend Google OAuth redirect (opens in same tab). */
  googleLoginUrl: () => `${API_BASE}/api/auth/google/login`,
};

/* -------------------------------------------------------------- products */

export const products = {
  search: (data: {
    query: string;
    category?: string | null;
    budget_min?: number | null;
    budget_max?: number | null;
    limit?: number;
    sort_by?: string;
  }) => request<SearchResponse>("/api/products/search", { method: "POST", body: data }),

  get: (id: string) => request<Product>(`/api/products/${encodeURIComponent(id)}`),

  /** Catalogue feed for the Explore landing state — no query required. */
  featured: (opts: { category?: string | null; limit?: number } = {}) => {
    const params = new URLSearchParams();
    if (opts.category) params.set("category", opts.category);
    params.set("limit", String(opts.limit ?? 24));
    const qs = params.toString();
    return request<SearchResponse>(`/api/products/featured${qs ? `?${qs}` : ""}`);
  },

  compare: (product_ids: string[]) =>
    request<ComparisonResult>("/api/products/compare", {
      method: "POST",
      body: { product_ids },
    }),

  suggestions: () =>
    request<{ categories: { category: string; count: number }[]; is_sample_data: boolean }>(
      "/api/products/list/suggestions",
    ),
};

/* ------------------------------------------------------ public offers API */

export const offers = {
  search: (query: string, category?: string) => {
    const params = new URLSearchParams({ query });
    if (category) params.set("category", category);
    return request<{ query: string; offers: RetailOffer[]; providers_queried: string[]; provider_errors: string[]; as_of: string }>(
      `/api/offers/search?${params.toString()}`,
    );
  },
  featured: (limit = 24) =>
    request<{ offers: FeaturedOffer[]; providers_queried: string[]; provider_errors: string[]; as_of: string }>(
      `/api/offers/featured?limit=${limit}`,
    ),
};

/* ------------------------------------------------------------ AI routes */

export const ai = {
  chat: (data: { message: string; conversation_id?: string | null }) =>
    request<ChatResponse>("/api/chat", { method: "POST", body: data }),

  recommend: (data: {
    query: string;
    category?: string | null;
    budget_max?: number | null;
    usage?: string[];
    preferences?: Record<string, unknown>;
    limit?: number;
  }) =>
    request<RecommendationResponse>("/api/recommendations", {
      method: "POST",
      body: data,
    }),

  analyzeReviews: (data: { product_id?: string; query?: string }) =>
    request<ReviewAnalysisResponse>("/api/reviews/analyze", {
      method: "POST",
      body: data,
    }),
};

/* --------------------------------------------------------- conversations */

export const conversations = {
  list: () => request<Conversation[]>("/api/conversations"),

  get: (id: string) =>
    request<ConversationDetail>(`/api/conversations/${encodeURIComponent(id)}`),

  remove: (id: string) =>
    request<void>(`/api/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
};

/* ------------------------------------------------------ saved/watchlist */

export const watchlist = {
  list: () => request<WatchlistEntry[]>("/api/watchlist"),

  add: (product_id: string, target_price?: number | null) =>
    request<WatchlistEntry>("/api/watchlist", {
      method: "POST",
      body: { product_id, target_price },
    }),

  remove: (product_id: string) =>
    request<void>(`/api/watchlist/${encodeURIComponent(product_id)}`, {
      method: "DELETE",
    }),

  refresh: () =>
    request<{ checked: number; results: unknown[] }>("/api/watchlist/refresh", {
      method: "POST",
    }),

  savedList: () => request<SavedProduct[]>("/api/watchlist/saved"),

  save: (product_id: string) =>
    request<SavedProduct>("/api/watchlist/saved", {
      method: "POST",
      body: { product_id },
    }),

  unsave: (product_id: string) =>
    request<void>(`/api/watchlist/saved/${encodeURIComponent(product_id)}`, {
      method: "DELETE",
    }),
};

/* --------------------------------------------------------------- health */

export const system = {
  health: () =>
    request<{ status: string; environment?: string; llm_mode?: string }>(
      "/api/health",
    ),
};

/**
 * Stream one chat turn over SSE.
 *
 * `onEvent` receives each parsed event; the full payload arrives on the
 * `message` event. Returns when the stream ends (or throws on HTTP failure).
 */
export async function streamChat(
  data: { message: string; conversation_id?: string | null },
  onEvent: (event: string, payload: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/chat?stream=true`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      signal,
    },
  );

  if (!res.ok || !res.body) {
    throw new ApiRequestError(res.status, "stream_failed", "Chat stream failed.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const emitFrame = (frame: string) => {
    if (!frame.trim()) return;
    let event = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    try { onEvent(event, JSON.parse(dataLines.join("\n"))); }
    catch { /* ignore malformed frame */ }
  };

  for (;;) {
    const { done, value } = await reader.read();
    buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      emitFrame(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  if (buffer.trim()) emitFrame(buffer);
}
