"use client";

/**
 * Floating research chatbot docked at the bottom of every page.
 *
 * A launcher bubble expands into a compact chat panel that calls the same
 * `/api/chat` endpoint as the full research page (conversation id is kept
 * so follow-ups share memory). Hidden on /chat itself — that route already
 * is the full-screen version of the same assistant.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUp,
  Bot,
  Loader2,
  MessageSquare,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { ai, ApiRequestError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

interface DockMessage {
  role: "user" | "assistant";
  text: string;
}

const GREETING: DockMessage = {
  role: "assistant",
  text: "Hi! I'm your ShopMate research agent. Ask me to find, compare or rank products — e.g. “best laptop under ₹60000”.",
};

const HIDDEN_ROUTES = ["/chat"];

export default function ChatDock() {
  const pathname = usePathname();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<DockMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const hidden = HIDDEN_ROUTES.some((r) => pathname?.startsWith(r));

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, open]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const res = await ai.chat({ message: text, conversation_id: conversationId });
      setConversationId(res.conversation_id);
      setMessages((m) => [...m, { role: "assistant", text: res.reply }]);
    } catch (err) {
      const msg =
        err instanceof ApiRequestError && err.status === 401
          ? "Please sign in to chat with the research agent."
          : err instanceof ApiRequestError
            ? err.message
            : "Something went wrong — please try again.";
      setMessages((m) => [...m, { role: "assistant", text: msg }]);
    } finally {
      setBusy(false);
    }
  };

  if (hidden) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-3 print:hidden">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.96 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="chat-dock-panel glass flex h-[26rem] w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl sm:w-96"
            data-testid="chat-dock-panel"
            role="dialog"
            aria-label="Research chat"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border bg-gradient-to-r from-accent/25 via-accent-2/15 to-[#a78bfa]/25 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-2 text-[#04101f]">
                  <Bot size={16} />
                </span>
                <div className="leading-tight">
                  <p className="text-sm font-semibold">Research agent</p>
                  <p className="flex items-center gap-1 text-[11px] text-muted">
                    <span className="status-dot bg-success text-success" />
                    {user ? `Signed in as ${user.full_name.split(" ")[0]}` : "Guest session"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Link
                  href="/chat"
                  className="rounded-lg p-1.5 text-muted transition hover:bg-surface-2 hover:text-accent"
                  aria-label="Open full research page"
                  title="Open full research page"
                >
                  <Sparkles size={15} />
                </Link>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded-lg p-1.5 text-muted transition hover:bg-surface-2 hover:text-foreground"
                  aria-label="Close chat"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div
              ref={scrollRef}
              className="scroll-thin flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4"
            >
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex max-w-[85%] items-start gap-2 ${
                    m.role === "user" ? "self-end flex-row-reverse" : "self-start"
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                      m.role === "user"
                        ? "bg-violet-500/25 text-violet-400"
                        : "bg-accent/20 text-accent"
                    }`}
                  >
                    {m.role === "user" ? <User size={12} /> : <Bot size={12} />}
                  </span>
                  <p
                    className={`whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                      m.role === "user"
                        ? "rounded-tr-sm bg-accent text-[#04101f]"
                        : "rounded-tl-sm bg-surface-2 text-foreground"
                    }`}
                  >
                    {m.text}
                  </p>
                </div>
              ))}
              {busy && (
                <div className="flex items-center gap-2 self-start text-xs text-muted">
                  <Loader2 size={13} className="animate-spin" /> Researching…
                </div>
              )}
            </div>

            {/* Composer */}
            <form
              onSubmit={send}
              className="flex items-center gap-2 border-t border-border p-3"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask the research agent…"
                className="input flex-1 !py-2 text-sm"
                aria-label="Chat message"
                data-testid="chat-dock-input"
              />
              <button
                type="submit"
                disabled={busy || !input.trim()}
                className="btn-primary !rounded-xl !p-2.5"
                aria-label="Send message"
                data-testid="chat-dock-send"
              >
                <ArrowUp size={16} />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Launcher */}
      <motion.button
        type="button"
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.94 }}
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close research chat" : "Open research chat"}
        data-testid="chat-dock-launcher"
        className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-accent via-accent-2 to-[#a78bfa] text-[#04101f] shadow-lg shadow-accent/30 transition"
      >
        <AnimatePresence mode="wait" initial={false}>
          {open ? (
            <motion.span key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }}>
              <X size={22} />
            </motion.span>
          ) : (
            <motion.span key="chat" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }}>
              <MessageSquare size={22} />
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  );
}
