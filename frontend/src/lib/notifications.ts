/** In-app notifications + optional email via gateway. Scout-done uses email + in-app only. */

export type NotifyKind =
  | "scout_done"
  | "intel_ready"
  | "studio_done"
  | "stage_ready"
  | "calendar_due"
  | "generic";

export type AppNotification = {
  id: string;
  kind: NotifyKind;
  title: string;
  body: string;
  href?: string;
  createdAt: string;
  read: boolean;
};

const STORAGE_KEY = "rivalradar.notifications";
const EMAIL_KEY = "rivalradar.notify.email";
const EVENT = "rivalradar:notifications";

function emit(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(EVENT));
}

export function subscribeNotifications(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function loadNotifications(): AppNotification[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as AppNotification[];
    return Array.isArray(parsed) ? parsed.slice(0, 50) : [];
  } catch {
    return [];
  }
}

function saveNotifications(rows: AppNotification[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(rows.slice(0, 50)));
  } catch {
    // private mode
  }
  emit();
}

export function unreadCount(rows = loadNotifications()): number {
  return rows.filter((n) => !n.read).length;
}

export function markNotificationRead(id: string): void {
  const next = loadNotifications().map((n) => (n.id === id ? { ...n, read: true } : n));
  saveNotifications(next);
}

export function markAllNotificationsRead(): void {
  saveNotifications(loadNotifications().map((n) => ({ ...n, read: true })));
}

export function getNotifyEmail(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(EMAIL_KEY)?.trim() ?? "";
  } catch {
    return "";
  }
}

export function setNotifyEmail(email: string): void {
  if (typeof window === "undefined") return;
  try {
    const v = email.trim();
    if (v) window.localStorage.setItem(EMAIL_KEY, v);
    else window.localStorage.removeItem(EMAIL_KEY);
  } catch {
    // ignore
  }
  emit();
}

export type PushNotificationInput = {
  kind: NotifyKind;
  title: string;
  body: string;
  href?: string;
  /** When true (default for scout_done), also POST /notify/email if an address is saved */
  email?: boolean;
};

export function pushNotification(input: PushNotificationInput): AppNotification {
  const row: AppNotification = {
    id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    kind: input.kind,
    title: input.title,
    body: input.body,
    href: input.href,
    createdAt: new Date().toISOString(),
    read: false,
  };
  saveNotifications([row, ...loadNotifications()]);

  const shouldEmail =
    input.email === true || (input.email !== false && input.kind === "scout_done");
  const to = getNotifyEmail();
  if (shouldEmail && to && typeof window !== "undefined") {
    const gateway = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";
    void fetch(`${gateway}/notify/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to,
        kind: input.kind,
        title: input.title,
        body: input.body,
        href: input.href ? `${window.location.origin}${input.href}` : undefined,
      }),
    }).catch(() => undefined);
  }
  return row;
}
