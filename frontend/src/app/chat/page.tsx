"use client";

/**
 * Research chat — runs the LangGraph workflow with SSE progress streaming.
 *
 * Product cards, ranked recommendations, agent trace and follow-ups are all
 * rendered from the real backend payload; nothing is fabricated client-side.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Bot,
  CheckCircle2,
  Loader2,
  Send,
  Sparkles,
  User,
  ChevronDown,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import AuthGuard from "@/components/AuthGuard";
import ProductCard from "@/components/ProductCard";
import { streamChat, conversations as conversationsApi, ApiRequestError } from "@/lib/api";
import type { ChatResponse, RankedProduct } from "@/lib/types";
import { factorLabel, formatPrice, scorePercent } from "@/lib/format";

interface Entry {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
  error?: string;
}

let seq = 0;

function ChatInner() {
  const params = useSearchParams();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(
    params.get("c"),
  );
  const [openTrace, setOpenTrace] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Deep link: ?q=… auto-sends the first message.
  const send = useCallback(async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    setStage("started");

    const userId = `u${++seq}`;
    setEntries((e) => [...e, { id: userId, role: "user", text: message }]);

    const assistantId = `a${++seq}`;
    let response: ChatResponse | null = null;
    let streamError: string | null = null;

    try {
      await streamChat(
        { message, conversation_id: conversationId },
        (event, payload) => {
          if (event === "status") {
            setStage(String(payload.message ?? "Researching…"));
          } else if (event === "progress") {
            setStage("Building your answer…");
          } else if (event === "message") {
            response = payload as unknown as ChatResponse;
          } else if (event === "error") {
            streamError =
              (payload as { message?: string }).message ?? "Research failed.";
          }
        },
      );
    } catch (err) {
      streamError =
        err instanceof ApiRequestError ? err.message : "Could not reach the server.";
    }

    setStage(null);
    setBusy(false);

    if (response) {
      const r = response as unknown as ChatResponse;
      setConversationId(r.conversation_id);
      setEntries((e) => [
        ...e,
        { id: assistantId, role: "assistant", text: r.reply, response: r },
      ]);
    } else {
      setEntries((e) => [
        ...e,
        {
          id: assistantId,
          role: "assistant",
          text: "Something went wrong running the research workflow.",
          error: streamError ?? "Unknown error",
        },
      ]);
    }
  }, [busy, conversationId, input]);

  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const existingId = params.get("c");
    if (existingId) {
      void conversationsApi.get(existingId).then((conversation) => {
        setConversationId(conversation.id);
        setEntries(conversation.messages.map((message) => {
          const meta = message.meta ?? {};
          const response = message.role === "assistant" ? {
            conversation_id: conversation.id,
            message_id: message.id,
            reply: message.content,
            intent: (meta.intent as string | null) ?? null,
            products: (meta.products as ChatResponse["products"]) ?? [],
            ranked: (meta.ranked as ChatResponse["ranked"]) ?? [],
            suggested_followups: (meta.suggested_followups as string[]) ?? [],
            trace: (meta.trace as ChatResponse["trace"]) ?? [],
            errors: (meta.errors as string[]) ?? [],
            llm_mode: (meta.llm_mode as string) ?? "unknown",
            created_at: message.created_at,
          } satisfies ChatResponse : undefined;
          return {
            id: message.id,
            role: message.role === "user" ? "user" as const : "assistant" as const,
            text: message.content,
            response,
          };
        }));
      }).catch((err: unknown) => {
        setEntries([{ id: `load-${Date.now()}`, role: "assistant", text: "Could not load this conversation.",
          error: err instanceof ApiRequestError ? err.message : "Please try again." }]);
      });
      return;
    }
    const q = params.get("q");
    if (q) window.setTimeout(() => void send(q), 0);
  }, [params, send]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, stage]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send();
  };

  const latest = [...entries].reverse().find((e) => e.role === "assistant")?.response;

  return (
    <>
      <Navbar />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 py-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">
              Research <span className="text-gradient">assistant</span>
            </h1>
            <p className="text-sm text-muted">
              Multi-agent graph · explainable ranking · persistent memory
            </p>
          </div>
          {conversationId && (
            <Link href="/history" className="btn-ghost text-sm">
              History
            </Link>
          )}
        </header>

        {/* Messages */}
        <section
          className="scroll-thin mt-6 flex-1 overflow-y-auto pr-1"
          style={{ maxHeight: "58vh" }}
          data-testid="chat-messages"
        >
          {entries.length === 0 && (
            <div className="card mt-6 p-6 text-center">
              <Sparkles className="mx-auto text-accent-2" />
              <p className="mt-3 font-semibold">Ask anything about buying</p>
              <p className="mt-1 text-sm text-muted">
                e.g. “Find a laptop under ₹60000 for gaming” or “Compare iPhone 15
                with Galaxy S24”.
              </p>
            </div>
          )}

          <div className="flex flex-col gap-4">
            {entries.map((entry) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-3 ${entry.role === "user" ? "justify-end" : ""}`}
              >
                {entry.role === "assistant" && (
                  <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent">
                    <Bot size={16} />
                  </span>
                )}
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    entry.role === "user"
                      ? "bg-accent text-background"
                      : "card"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{entry.text}</p>
                  {entry.error && (
                    <p className="mt-2 text-danger">{entry.error}</p>
                  )}
                </div>
                {entry.role === "user" && (
                  <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-muted">
                    <User size={16} />
                  </span>
                )}
              </motion.div>
            ))}

            {busy && (
              <div className="flex items-center gap-2 text-sm text-muted">
                <Loader2 size={15} className="animate-spin text-accent-2" />
                {stage ?? "Starting research…"}
              </div>
            )}
          </div>

          {/* Products from the latest turn */}
          {latest && latest.products.length > 0 && (
            <section className="mt-5">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
                Products found
              </h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {latest.products.map((p) => (
                  <ProductCard key={p.product_id} product={p} />
                ))}
              </div>
            </section>
          )}

          {/* Ranked recommendations with factor breakdown */}
          {latest && latest.ranked.length > 0 && (
            <section className="mt-5">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
                Ranked for you
              </h2>
              <div className="mt-3 flex flex-col gap-3">
                {latest.ranked.slice(0, 5).map((r: RankedProduct, i: number) => (
                  <RankedRow key={r.product.product_id} rank={i + 1} item={r} />
                ))}
              </div>
            </section>
          )}

          {/* Agent trace */}
          {latest && latest.trace.length > 0 && (
            <section className="mt-5">
              <button
                type="button"
                onClick={() => setOpenTrace((v) => !v)}
                className="btn-ghost flex w-full items-center justify-between text-sm"
                data-testid="trace-toggle"
              >
                <span>Agent trace ({latest.trace.length} steps · {latest.llm_mode})</span>
                <ChevronDown size={15} className={openTrace ? "rotate-180" : ""} />
              </button>
              {openTrace && (
                <ol className="mt-2 flex flex-col gap-1.5 rounded-xl border border-border p-3 text-xs text-muted">
                  {latest.trace.map((t, idx) => (
                    <li key={idx} className="flex gap-2">
                      <span className="text-accent-2">▸</span>
                      <span>
                        <strong className="text-foreground">
                          {String(t.node ?? t.stage ?? "step")}
                        </strong>
                        {t.detail ? ` — ${t.detail}` : t.message ? ` — ${t.message}` : ""}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          )}

          {/* Follow-ups */}
          {latest && latest.suggested_followups.length > 0 && (
            <section className="mt-5 flex flex-wrap gap-2">
              {latest.suggested_followups.map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => void send(f)}
                  className="badge hover:border-accent hover:text-accent"
                >
                  {f}
                </button>
              ))}
            </section>
          )}

          {/* Sample-data honesty note */}
          {latest && latest.errors.length > 0 && (
            <p className="mt-4 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
              {latest.errors.join(" · ")}
            </p>
          )}

          <div ref={bottomRef} />
        </section>

        {/* Composer */}
        <form onSubmit={onSubmit} className="mt-4 flex gap-2" data-testid="chat-form">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about products, comparisons, reviews…"
            className="input flex-1"
            aria-label="Message"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="btn-primary flex items-center gap-2"
            data-testid="chat-send"
          >
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            <span className="hidden sm:inline">Send</span>
          </button>
        </form>
        <p className="mt-2 text-center text-xs text-muted">
          Responses are computed by the research graph from real data — sample
          listings are labelled “Sample data”.
        </p>
      </main>
    </>
  );
}

function RankedRow({ rank, item }: { rank: number; item: RankedProduct }) {
  const [open, setOpen] = useState(false);
  const pct = scorePercent(item.final_score);

  return (
    <div className="card p-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 text-left"
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15 text-xs font-bold text-accent">
          {rank}
        </span>
        <span className="flex-1">
          <span className="block text-sm font-semibold">{item.product.title}</span>
          <span className="text-xs text-muted">
            {formatPrice(item.product.price, item.product.currency)} ·{" "}
            {item.product.merchant}
          </span>
        </span>
        <span className="text-right">
          <span className="block text-sm font-bold text-gradient">{pct}%</span>
          <span className="text-[10px] uppercase text-muted">match</span>
        </span>
        <ChevronDown size={15} className={open ? "rotate-180" : ""} />
      </button>

      {open && (
        <div className="mt-3 border-t border-border pt-3">
          <div className="flex flex-wrap gap-2">
            {Object.entries(item.factor_scores).map(([k, v]) => (
              <span key={k} className="badge" title={factorLabel(k)}>
                {factorLabel(k)} {scorePercent(v)}%
              </span>
            ))}
          </div>
          <ul className="mt-3 flex flex-col gap-1 text-xs text-muted">
            {item.reasons.map((r, i) => (
              <li key={i} className="flex gap-2">
                <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-success" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  return (
    <AuthGuard>
      <Suspense fallback={<div className="p-10 text-center text-muted">Loading…</div>}>
        <ChatInner />
      </Suspense>
    </AuthGuard>
  );
}
