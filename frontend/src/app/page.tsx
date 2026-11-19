"use client";

/**
 * Landing page — 3D hero, brand marquee, capability grid, how-it-works
 * and CTA. Motion: Framer Motion entrances + a GSAP scroll-triggered
 * pipeline strip; the hero geometry is a lazy Three.js scene.
 */

import Link from "next/link";
import dynamic from "next/dynamic";
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

// Three.js is client-only; ssr:false keeps it out of the server bundle.
const HeroScene = dynamic(() => import("@/components/HeroScene"), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-full w-full items-center justify-center rounded-2xl border border-border bg-gradient-to-br from-accent/25 via-accent-2/15 to-[#a78bfa]/25"
      aria-hidden
    >
      <Sparkles className="animate-pulse text-accent-2" size={40} />
    </div>
  ),
});

const FEATURES = [
  {
    icon: MessageSquare,
    title: "Agentic research",
    text: "A LangGraph workflow routes each question through only the agents it needs — search, compare, reviews, specs, advice.",
    hue: "from-cyan-500/25 to-blue-500/10",
    iconColor: "text-cyan-400",
  },
  {
    icon: GitCompareArrows,
    title: "Honest comparisons",
    text: "Side-by-side diffs flag missing specs and stale data instead of pretending every field is known.",
    hue: "from-pink-500/25 to-rose-500/10",
    iconColor: "text-pink-400",
  },
  {
    icon: LineChart,
    title: "Explainable ranking",
    text: "Every score breaks down into spec, budget, preference and review factors — with reasons you can read.",
    hue: "from-violet-500/25 to-indigo-500/10",
    iconColor: "text-violet-400",
  },
  {
    icon: Tags,
    title: "Labelled sample data",
    text: "Demo listings are clearly badged. Merchant connectors report `not_configured` rather than inventing prices.",
    hue: "from-amber-500/25 to-orange-500/10",
    iconColor: "text-amber-400",
  },
  {
    icon: BrainCircuit,
    title: "Persistent memory",
    text: "Your budget, usage and requirements carry across turns of a conversation — and never leak between users.",
    hue: "from-emerald-500/25 to-teal-500/10",
    iconColor: "text-emerald-400",
  },
  {
    icon: ShieldCheck,
    title: "Backend-owned auth",
    text: "Real Google OAuth + bcrypt passwords + httpOnly JWT. The API validates sessions independently of the UI.",
    hue: "from-blue-500/25 to-sky-500/10",
    iconColor: "text-blue-400",
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

/** Brand names present in the labelled sample catalogue. */
const BRANDS = [
  "Aurora",
  "Nimbus",
  "Titan",
  "Scholar",
  "Apple",
  "Samsung",
  "OnePlus",
  "SonicWave",
  "BassPulse",
  "StudioReference",
  "EchoPods",
  "PulseFit",
  "Apex",
  "Vision",
  "Nova",
  "Velocity",
  "Lumina",
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
        {/* Hero — copy left, live Three.js scene right */}
        <section className="bg-grid bg-glow relative overflow-hidden">
          <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-16 sm:py-20 lg:grid-cols-2 lg:gap-6 lg:py-24">
            <div className="text-center lg:text-left">
              <motion.span
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="badge mx-auto inline-block lg:mx-0"
              >
                <Sparkles size={12} className="mr-1 inline text-accent-2" />
                Autonomous agentic shopping intelligence
              </motion.span>

              <motion.h1
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08, duration: 0.55 }}
                className="mx-auto mt-6 max-w-2xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:mx-0 lg:text-6xl"
              >
                Shop smarter with an AI that{" "}
                <span className="text-gradient">shows its work</span>
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.16, duration: 0.55 }}
                className="mx-auto mt-6 max-w-xl text-lg text-muted lg:mx-0"
              >
                ShopMate AI runs a multi-agent research graph over real product
                data — then explains every recommendation factor by factor. No
                black boxes, no invented prices.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.24, duration: 0.55 }}
                className="mt-9 flex flex-wrap items-center justify-center gap-3 lg:justify-start"
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
                Works fully offline with the labelled sample dataset — no API
                keys required.
              </motion.p>
            </div>

            {/* 3D scene */}
            <motion.div
              initial={{ opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2, duration: 0.7 }}
              className="relative mx-auto h-[320px] w-full max-w-xl sm:h-[400px] lg:h-[460px]"
            >
              <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-accent/15 via-transparent to-[#a78bfa]/15 blur-2xl" />
              <HeroScene />
            </motion.div>
          </div>

          {/* Stats ribbon */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45 }}
            className="mx-auto grid max-w-4xl grid-cols-2 gap-3 px-4 pb-14 sm:grid-cols-4"
          >
            {[
              { value: "7", label: "specialist agents", color: "text-cyan-400" },
              { value: "4", label: "ranking factors", color: "text-violet-400" },
              { value: "6", label: "product categories", color: "text-emerald-400" },
              { value: "100%", label: "explainable scores", color: "text-amber-400" },
            ].map((s) => (
              <div
                key={s.label}
                className="card px-4 py-3 text-center backdrop-blur"
              >
                <div className={`text-2xl font-black ${s.color}`}>{s.value}</div>
                <div className="mt-0.5 text-xs text-muted">{s.label}</div>
              </div>
            ))}
          </motion.div>
        </section>

        {/* Brand marquee — the catalogue's naming section */}
        <section
          className="border-y border-border bg-surface/40 py-7"
          aria-label="Brands in the catalogue"
        >
          <p className="mb-4 text-center text-xs font-semibold uppercase tracking-[0.2em] text-muted">
            Brands in the sample catalogue
          </p>
          <div className="marquee-mask relative overflow-hidden">
            <div className="marquee-track gap-3">
              {[...BRANDS, ...BRANDS].map((brand, i) => (
                <span
                  key={`${brand}-${i}`}
                  className="badge whitespace-nowrap px-4 py-2 text-sm"
                >
                  {brand}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* Features */}
        <section className="mx-auto max-w-7xl px-4 py-20">
          <h2 className="text-center text-3xl font-bold">
            Built for <span className="text-gradient">trustworthy decisions</span>
          </h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, text, hue, iconColor }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ delay: i * 0.05, duration: 0.4 }}
                className={`card group relative overflow-hidden p-5 transition hover:-translate-y-1 hover:shadow-lg`}
              >
                <div
                  className={`absolute inset-x-0 top-0 h-24 bg-gradient-to-b ${hue} opacity-60 transition group-hover:opacity-100`}
                  aria-hidden
                />
                <div className="relative">
                  <span
                    className={`inline-flex rounded-xl bg-surface/80 p-2.5 ${iconColor}`}
                  >
                    <Icon size={22} />
                  </span>
                  <h3 className="mt-3 font-semibold">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{text}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Agent pipeline (GSAP scroll reveal) */}
        <section ref={pipelineRef} className="border-y border-border bg-surface/60 py-16">
          <div className="mx-auto max-w-6xl px-4 text-center">
            <h2 className="text-2xl font-bold">
              One query, <span className="text-gradient">seven specialists</span>
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-muted">
              A conditional router picks the branches your question actually
              needs — and parallel branches run in the same step.
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
        <section className="bg-glow mx-auto max-w-4xl px-4 py-24 text-center">
          <motion.h2
            initial={{ opacity: 0, scale: 0.97 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="text-3xl font-bold"
          >
            Your next purchase,{" "}
            <span className="text-gradient">fully researched</span>
          </motion.h2>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
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
      {/* Site footer comes from the root layout. */}
    </>
  );
}
