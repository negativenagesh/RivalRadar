"use client";

import { CalendarRemindWatcher } from "@/components/calendar-remind-watcher";
import { OperatorModelsProvider } from "@/components/operator-models-provider";
import { VisitorTracker } from "@/components/visitor-tracker";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <OperatorModelsProvider>
      <VisitorTracker />
      <CalendarRemindWatcher />
      {children}
    </OperatorModelsProvider>
  );
}
