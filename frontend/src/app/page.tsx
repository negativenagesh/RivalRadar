"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "motion/react";
import {
  Eye,
  Layers,
  PenLine,
  ShieldCheck,
  MonitorPlay,
  Sparkles,
  Lock,
} from "lucide-react";

import { NavBar } from "@/components/nav-bar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const CATEGORIES = ["DTC", "SaaS", "Creator brands", "Fintech", "Beauty", "AI tools"];

const TIMELINE = [
  {
    icon: Eye,
    title: "Watch",
    body: "Scout rival feeds live — posts, formats, hooks — while you watch the browser move.",
  },
  {
    icon: Layers,
    title: "Cluster",
    body: "Group what’s winning this week: memes, launches, founder POV, UGC spikes.",
  },
  {
    icon: PenLine,
    title: "Draft",
    body: "Spin on-brand captions + visual concepts in your voice, not ChatGPT bland.",
  },
  {
    icon: ShieldCheck,
    title: "Approve",
    body: "You gate every ship. Compliance flags first. Nothing posts itself.",
  },
];

const INPUTS = [
  "Company website",
  "LinkedIn / X / IG / TikTok / YouTube",
  "3+ competitor links",
  "Brand voice notes",
  "Do-not-say list",
  "Preferred formats",
];

const ARSENAL = [
  "Reply / response posts",
  "Trend-jack originals",
  "Quote-tweet angles",
  "Carousel / thread outlines",
  "Meme + image concepts",
  "Founder POV notes",
  "Comment suggestions (opt-in)",
  "Internal rival compare slides",
];

const SAMPLES = [
  {
    label: "Response draft",
    caption:
      "They’re flexing features. We’re flexing outcomes. Same week, louder receipts.",
    concept: "Split-screen product UI vs rival claim, lime accent ticks",
  },
  {
    label: "Meme concept",
    caption: "POV: your competitor just posted the exact take you drafted yesterday.",
    concept: "Phone lockscreen notification collage, chaotic-good energy",
  },
];

function MegaCta({ className }: { className?: string }) {
  return (
    <Button
      size="lg"
      asChild
      className={`h-14 px-8 text-base font-semibold shadow-[0_0_40px_-8px_oklch(0.87_0.24_128)] transition-transform hover:scale-[1.02] active:scale-[0.99] ${className ?? ""}`}
    >
      <Link href="/mission">Be the superpower in your category</Link>
    </Button>
  );
}

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <NavBar />
      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="absolute inset-0">
            <Image
              src="/hero-radar.png"
              alt=""
              fill
              priority
              className="object-cover object-center"
              sizes="100vw"
            />
            <div className="absolute inset-0 bg-gradient-to-b from-background/70 via-background/85 to-background" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,var(--background)_75%)]" />
          </div>

          <div className="relative mx-auto flex max-w-4xl flex-col items-center px-6 pt-10 pb-16 text-center sm:pt-12 sm:pb-24">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="mb-3 text-3xl font-bold tracking-tight sm:text-4xl"
            >
              Rival<span className="text-primary">Radar</span>
            </motion.p>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.05 }}
              className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-primary"
            >
              Become the loudest smart brand in your niche
            </motion.p>
            <motion.h1
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.08 }}
              className="text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl"
            >
              They post the trend.
              <br />
              You own the <span className="text-primary">timeline</span>.
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.12 }}
              className="mt-5 max-w-lg text-base text-muted-foreground sm:text-lg"
            >
              Watch rivals. Spot the gap. Draft the comeback — caption, visual, safety check —
              while a human still holds the publish button.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.18 }}
              className="mt-10 flex flex-col items-center gap-4"
            >
              <MegaCta />
              <div className="flex gap-4 text-sm text-muted-foreground">
                <Link href="/digest" className="hover:text-foreground">
                  Digest
                </Link>
                <span aria-hidden>·</span>
                <Link href="/review" className="hover:text-foreground">
                  Review
                </Link>
              </div>
            </motion.div>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.35 }}
              className="mt-8 flex items-center gap-2 rounded-full border border-border/60 bg-background/50 px-3 py-1.5 text-xs text-muted-foreground backdrop-blur"
            >
              <Lock className="size-3 text-primary" />
              Never auto-posts. You approve every draft.
            </motion.div>
          </div>
        </section>

        {/* FOMO / social proof */}
        <section className="border-y border-border/40 bg-muted/20 py-4">
          <div className="mx-auto flex max-w-5xl flex-col items-center gap-3 px-6 sm:flex-row sm:justify-between">
            <p className="text-sm font-medium">
              While you slept,{" "}
              <span className="text-primary">12 rival posts</span> dropped. Built for brands
              that reply in public.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {CATEGORIES.map((c) => (
                <Badge key={c} variant="secondary" className="font-normal">
                  {c}
                </Badge>
              ))}
            </div>
          </div>
        </section>

        {/* Timeline */}
        <section className="mx-auto max-w-5xl px-6 py-20">
          <h2 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">
            How it hits different
          </h2>
          <p className="mx-auto mt-2 max-w-md text-center text-sm text-muted-foreground">
            Four beats. Zero autopilot publishing.
          </p>
          <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {TIMELINE.map((step, i) => (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.4, delay: i * 0.06 }}
                className="relative"
              >
                <step.icon className="mb-3 size-5 text-primary" />
                <p className="font-mono text-xs text-primary">0{i + 1}</p>
                <h3 className="mt-1 text-lg font-bold">{step.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{step.body}</p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Live scout teaser */}
        <section className="mx-auto max-w-5xl px-6 pb-20">
          <div className="overflow-hidden rounded-2xl border border-border/60 bg-card/40">
            <div className="flex items-center gap-2 border-b border-border/60 bg-muted/30 px-4 py-2.5">
              <span className="size-2.5 rounded-full bg-destructive/80" />
              <span className="size-2.5 rounded-full bg-chart-2" />
              <span className="size-2.5 rounded-full bg-primary" />
              <span className="ml-3 font-mono text-xs text-muted-foreground">
                live scout · headless browser
              </span>
            </div>
            <div className="relative flex min-h-[200px] flex-col items-center justify-center gap-3 bg-[radial-gradient(circle_at_30%_40%,oklch(0.87_0.24_128_/_0.08),transparent_50%)] p-10 text-center">
              <MonitorPlay className="size-10 text-primary/80" />
              <h3 className="text-xl font-bold">Watch the agent browse rivals live</h3>
              <p className="max-w-md text-sm text-muted-foreground">
                Screenshots stream as it scrolls feeds. Optional session recording so your team
                can replay the scout later.
              </p>
            </div>
          </div>
        </section>

        {/* What we need */}
        <section className="border-y border-border/40 bg-muted/10 py-20">
          <div className="mx-auto max-w-5xl px-6">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              What we need from you
            </h2>
            <p className="mt-2 max-w-lg text-sm text-muted-foreground">
              Bring context. The agent can&apos;t invent your brand — feed it links and voice.
            </p>
            <ul className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {INPUTS.map((item) => (
                <li
                  key={item}
                  className="flex items-center gap-2 text-sm before:block before:size-1.5 before:rounded-full before:bg-primary"
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Creative arsenal */}
        <section className="mx-auto max-w-5xl px-6 py-20">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-primary" />
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Creative arsenal</h2>
          </div>
          <p className="mt-2 max-w-lg text-sm text-muted-foreground">
            What RivalRadar can propose. Comment / reply suggestions stay off until you flip
            them on.
          </p>
          <div className="mt-8 flex flex-wrap gap-2">
            {ARSENAL.map((item) => (
              <Badge key={item} variant="outline" className="px-3 py-1.5 text-sm font-normal">
                {item}
              </Badge>
            ))}
          </div>
        </section>

        {/* Sample outputs */}
        <section className="mx-auto max-w-5xl px-6 pb-20">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Sample heat</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Drafts look like this before they hit your review queue.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {SAMPLES.map((s) => (
              <div
                key={s.label}
                className="rounded-xl border border-border/60 bg-card/50 p-5 transition hover:border-primary/40"
              >
                <p className="text-xs font-semibold uppercase tracking-wider text-primary">
                  {s.label}
                </p>
                <p className="mt-3 text-base font-medium leading-snug">&ldquo;{s.caption}&rdquo;</p>
                <p className="mt-3 text-xs text-muted-foreground">Visual: {s.concept}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Trust */}
        <section className="border-y border-border/40 bg-muted/10 py-16">
          <div className="mx-auto max-w-3xl px-6 text-center">
            <ShieldCheck className="mx-auto size-8 text-primary" />
            <h2 className="mt-4 text-2xl font-bold">Trust is the product</h2>
            <p className="mt-3 text-sm text-muted-foreground">
              Brand-safety pass on every caption. Recording is opt-in. Comments stay suggestions
              until you allow them. Nothing ships without a human yes.
            </p>
          </div>
        </section>

        {/* Final CTA */}
        <section className="mx-auto flex max-w-3xl flex-col items-center px-6 py-24 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Ready to own your category?
          </h2>
          <p className="mt-3 text-muted-foreground">
            Plug in your brand + rivals. Start the scout. Stay in the loop.
          </p>
          <div className="mt-8">
            <MegaCta />
          </div>
        </section>
      </main>

      <footer className="border-t border-border/60 py-8 text-center text-sm text-muted-foreground">
        <p>A human approves every draft before it ships. Nothing here posts on its own.</p>
        <a
          href="https://github.com/negativenagesh/RivalRadar"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-primary hover:underline"
        >
          GitHub
        </a>
      </footer>
    </div>
  );
}
