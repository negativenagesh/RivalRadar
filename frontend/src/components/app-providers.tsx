"use client";

import { OperatorModelsProvider } from "@/components/operator-models-provider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return <OperatorModelsProvider>{children}</OperatorModelsProvider>;
}
