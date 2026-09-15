"use client";

import { OperatorModelsProvider } from "@/components/operator-models-provider";
import { VisitorTracker } from "@/components/visitor-tracker";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <OperatorModelsProvider>
      <VisitorTracker />
      {children}
    </OperatorModelsProvider>
  );
}
