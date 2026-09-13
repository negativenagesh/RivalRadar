"use client";

import { createContext, useContext, useMemo, useSyncExternalStore, type ReactNode } from "react";

import {
  GEMINI_KEY_EVENT,
  clearGeminiKey as persistClear,
  hasGeminiKey,
  loadGeminiKey,
  maskGeminiKey,
  saveGeminiKey,
} from "@/lib/gemini-key";

type GeminiKeyContextValue = {
  key: string;
  masked: string;
  ready: boolean;
  setKey: (raw: string) => void;
  clear: () => void;
};

const GeminiKeyContext = createContext<GeminiKeyContextValue | null>(null);

function subscribe(onStoreChange: () => void) {
  window.addEventListener(GEMINI_KEY_EVENT, onStoreChange);
  window.addEventListener("storage", onStoreChange);
  return () => {
    window.removeEventListener(GEMINI_KEY_EVENT, onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}

function getSnapshot() {
  return loadGeminiKey();
}

function getServerSnapshot() {
  return "";
}

export function GeminiKeyProvider({ children }: { children: ReactNode }) {
  const key = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const value = useMemo<GeminiKeyContextValue>(
    () => ({
      key,
      masked: maskGeminiKey(key),
      ready: hasGeminiKey(key),
      setKey: (raw: string) => {
        saveGeminiKey(raw);
      },
      clear: () => persistClear(),
    }),
    [key],
  );

  return <GeminiKeyContext.Provider value={value}>{children}</GeminiKeyContext.Provider>;
}

export function useGeminiKey(): GeminiKeyContextValue {
  const ctx = useContext(GeminiKeyContext);
  if (!ctx) {
    throw new Error("useGeminiKey must be used inside GeminiKeyProvider");
  }
  return ctx;
}
