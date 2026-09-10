"use client";

import Link from "next/link";
import { motion } from "motion/react";

import { NavBar } from "@/components/nav-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

const STEPS = [
  {
    title: "Watch",
    body: "Ingests competitor posts and clusters them by format and theme — memes, launches, founder posts, UGC.",
  },
  {
    title: "Draft",
    body: "Generates on-brand captions and image concepts, voice-matched against your own past posts.",
  },
  {
    title: "Check",
    body: "Every draft runs through a brand-safety pass — banned claims, off-brand tone — before a human sees it.",
  },
  {
    title: "Approve",
    body: "You review, edit, or reject. Nothing ships without a human saying yes.",
  },
];

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <NavBar />
      <main className="flex-1">
        <section className="mx-auto flex max-w-4xl flex-col items-start px-6 pt-24 pb-20 sm:pt-32">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="mb-4 text-sm font-semibold uppercase tracking-widest text-primary"
          >
            Competitor intelligence, on autopilot
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05 }}
            className="text-5xl font-bold leading-[1.05] tracking-tight sm:text-7xl"
          >
            They post the trend.
            <br />
            You post the <span className="text-primary">response</span>.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mt-6 max-w-xl text-lg text-muted-foreground"
          >
            RivalRadar watches your competitors&apos; social content, spots what&apos;s working, and
            drafts your on-brand comeback — caption, visual concept, brand-safety check — before you&apos;ve
            finished your coffee. You still approve every single post.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="mt-10 flex gap-4"
          >
            <Button size="lg" asChild>
              <Link href="/digest">See this week&apos;s digest</Link>
            </Button>
            <Button size="lg" variant="secondary" asChild>
              <Link href="/review">Review queue</Link>
            </Button>
          </motion.div>
        </section>

        <section className="mx-auto max-w-5xl px-6 pb-24">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                whileHover={{ y: -4 }}
              >
                <Card className="h-full border-border/60 bg-card/60">
                  <CardHeader>
                    <span className="text-sm font-mono text-primary">0{i + 1}</span>
                    <h3 className="text-xl font-bold">{step.title}</h3>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{step.body}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </section>
      </main>
      <footer className="border-t border-border/60 py-8 text-center text-sm text-muted-foreground">
        A human approves every draft before it ships. Nothing here posts on its own.
      </footer>
    </div>
  );
}
