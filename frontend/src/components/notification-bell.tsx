"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  getNotifyEmail,
  loadNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  setNotifyEmail,
  subscribeNotifications,
  unreadCount,
  type AppNotification,
} from "@/lib/notifications";

function snapshot(): string {
  return JSON.stringify(loadNotifications());
}

export function NotificationBell() {
  const raw = useSyncExternalStore(subscribeNotifications, snapshot, () => "[]");
  const rows = JSON.parse(raw) as AppNotification[];
  const unread = unreadCount(rows);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState(() => getNotifyEmail());

  return (
    <div className="relative">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="relative gap-1.5"
        onClick={() => {
          if (!open) setEmail(getNotifyEmail());
          setOpen((v) => !v);
        }}
        aria-label="Notifications"
      >
        <Bell className="size-3.5" />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </Button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-border/60 bg-background p-3 shadow-lg sm:w-96">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="font-ui text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Notifications
            </p>
            <button
              type="button"
              className="text-xs text-primary hover:underline"
              onClick={() => markAllNotificationsRead()}
            >
              Mark all read
            </button>
          </div>
          <label className="mb-3 block space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Email for Scout done (optional)
            </span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => setNotifyEmail(email)}
              placeholder="you@company.com"
              className="w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm"
            />
          </label>
          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {rows.length === 0 && (
              <li className="text-sm text-muted-foreground">No notifications yet.</li>
            )}
            {rows.map((n) => (
              <li
                key={n.id}
                className={
                  n.read
                    ? "rounded-lg border border-border/40 px-2 py-2 text-sm opacity-70"
                    : "rounded-lg border border-primary/30 bg-primary/5 px-2 py-2 text-sm"
                }
              >
                <button
                  type="button"
                  className="w-full text-left"
                  onClick={() => markNotificationRead(n.id)}
                >
                  <p className="font-medium text-foreground">{n.title}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{n.body}</p>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {new Date(n.createdAt).toLocaleString()}
                  </p>
                </button>
                {n.href && (
                  <Link
                    href={n.href}
                    className="mt-1 inline-block text-xs text-primary hover:underline"
                    onClick={() => {
                      markNotificationRead(n.id);
                      setOpen(false);
                    }}
                  >
                    Open →
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
