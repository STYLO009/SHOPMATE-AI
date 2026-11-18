"use client";

/**
 * Landing page — hero, capability grid, how-it-works and CTA.
 * Motion: Framer Motion entrances + a GSAP scroll-triggered pipeline strip.
 */

import Link from "next/link";
import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
  ArrowRight,
  BrainCircuit,
  GitCompareArrows,
  LineChart,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Tags,
} from "lucide-react";
import Navbar from "@/components/Navbar";

const FEATURES = [
  {
    icon: MessageSquare,
    title: "Agentic research",
    text: "A LangGraph workflow routes each question through only the agents it needs — search, compare, reviews, specs, advice.",
  },
  {
    icon: GitCompareArrows,
    title: "Honest comparisons",
    text: "Side-by-side diffs flag missing specs and stale data instead of pretending every field is known.",
  },
  {
    icon: LineChart,
    title: "Explainable ranking",
    text: "Every score breaks down into spec, budget, preference and review factors — with reasons you can read.",
  },
  {
    icon: Tags,
    title: "Labelled sample data",
    text: "Demo listings are clearly badged. Merchant connectors report `not_configured` rather than inventing prices.",
  },
  {
    icon: BrainCircuit,
    title: "Persistent memory",
    text: "Your budget, usage and requirements carry across turns of a conversation — and never leak between users.",
  },
  {
    icon: ShieldCheck,
    title: "Backend-owned auth",
    text: "Real Google OAuth + bcrypt passwords + httpOnly JWT. The API validates sessions independently of the UI.",
  },
];

const PIPELINE = [
  "Understand",
  "Route",
  "Search",
  "Review",
  "Specs",
  "Rank",
  "Advise",
];

export default function LandingPage() {
  const pipelineRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);
    const ctx = gsap.context(() => {
      gsap.from(".pipeline-step", {
        opacity: 0,
        y: 24,
        stagger: 0.1,
        duration: 0.5,
        ease: "power2.out",
        scrollTrigger: {
          trigger: pipelineRef.current,
          start: "top 78%",
        },
      });
    }, pipelineRef);
    return () => ctx.revert();
  }, []);

  return (
    <>
      <Navbar />
      <main className="flex-1">
        {/* Hero */}
        <section className="bg-grid bg-glow relative overflow-hidden">
          <div className="mx-auto max-w-7xl px-4 py-24 text-center sm:py-32">
            <motion.span
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              className="badge mx-auto inline-block"
            >
              <Sparkles size={12} className="mr-1 inline text-accent-2" />
              Autonomous agentic shopping intelligence
            </motion.span>

            <motion.h1
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08, duration: 0.55 }}
              className="mx-auto mt-6 max-w-4xl text-4xl font-bold leading-tight tracking-tight sm:text-6xl"
            >
              Shop smarter with an AI that <span className="text-gradient">shows its work</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.16, duration: 0.55 }}
              className="mx-auto mt-6 max-w-2xl text-lg text-muted"
            >
              ShopMate AI runs a multi-agent research graph over real product data —
              then explains every recommendation factor by factor. No black boxes,
              no invented prices.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.24, duration: 0.55 }}
              className="mt-9 flex flex-wrap items-center justify-center gap-3"
            >
              <Link href="/signup" className="btn-primary flex items-center gap-2">
                Start researching <ArrowRight size={16} />
              </Link>
              <Link href="/login" className="btn-ghost">
                Sign in
              </Link>
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="mt-4 text-sm text-muted"
            >
              Works fully offline with the labelled sample dataset — no API keys required.
            </motion.p>
          </div>
        </section>

        {/* Features */}
        <section className="mx-auto max-w-7xl px-4 py-20">
          <h2 className="text-center text-3xl font-bold">Built for trustworthy decisions</h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, text }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ delay: i * 0.05, duration: 0.4 }}
                className="card p-5"
              >
                <Icon size={22} className="text-accent-2" />
                <h3 className="mt-3 font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{text}</p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Agent pipeline (GSAP scroll reveal) */}
        <section ref={pipelineRef} className="border-y border-border bg-surface/60 py-16">
          <div className="mx-auto max-w-6xl px-4 text-center">
            <h2 className="text-2xl font-bold">One query, seven specialists</h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-muted">
              A conditional router picks the branches your question actually needs —
              and parallel branches run in the same step.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              {PIPELINE.map((step, i) => (
                <div
                  key={step}
                  className="pipeline-step card flex items-center gap-2 px-4 py-2.5 text-sm font-medium"
                >
                  <span className="text-accent-2">{i + 1}</span>
                  {step}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-4xl px-4 py-24 text-center">
          <motion.h2
            initial={{ opacity: 0, scale: 0.97 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="text-3xl font-bold"
          >
            Your next purchase, <span className="text-gradient">fully researched</span>
          </motion.h2>
          <div className="mt-7 flex justify-center gap-3">
            <Link href="/signup" className="btn-primary">
              Create a free account
            </Link>
            <Link href="/explore" className="btn-ghost">
              Browse products
            </Link>
              <Link href="/deals" className="btn-ghost">
                View live deals
              </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-8 text-center text-sm text-muted">
        ShopMate AI · demo platform · sample data is labelled and never presented as live
      </footer>
    </>
  );
}
