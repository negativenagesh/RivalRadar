"use client";

import { GeminiKeyProvider } from "@/components/gemini-key-provider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return <GeminiKeyProvider>{children}</GeminiKeyProvider>;
}
