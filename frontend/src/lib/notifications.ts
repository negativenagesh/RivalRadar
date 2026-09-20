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
/** Scout-done payload waiting for an email address to be saved in the bell. */
const PENDING_EMAIL_KEY = "rivalradar.notify.pending";
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

type PendingEmailPayload = {
  kind: NotifyKind;
  title: string;
  body: string;
  href?: string;
};

function gatewayBase(): string {
  return process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";
}

function postNotifyEmail(to: string, payload: PendingEmailPayload): void {
  if (typeof window === "undefined") return;
  void fetch(`${gatewayBase()}/notify/email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      to,
      kind: payload.kind,
      title: payload.title,
      body: payload.body,
      href: payload.href ? `${window.location.origin}${payload.href}` : undefined,
    }),
  }).catch((err: unknown) => {
    console.warn("[rivalradar] notify email POST failed", err);
  });
}

function readPending(): PendingEmailPayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(PENDING_EMAIL_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingEmailPayload;
    if (!parsed?.kind || !parsed?.title || !parsed?.body) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writePending(payload: PendingEmailPayload | null): void {
  if (typeof window === "undefined") return;
  try {
    if (payload) window.localStorage.setItem(PENDING_EMAIL_KEY, JSON.stringify(payload));
    else window.localStorage.removeItem(PENDING_EMAIL_KEY);
  } catch {
    // ignore
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
  const to = email.trim();
  if (to.includes("@")) {
    const pending = readPending();
    if (pending) {
      postNotifyEmail(to, pending);
      writePending(null);
    }
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
  if (shouldEmail && typeof window !== "undefined") {
    const payload: PendingEmailPayload = {
      kind: input.kind,
      title: input.title,
      body: input.body,
      href: input.href,
    };
    const to = getNotifyEmail();
    if (to) {
      postNotifyEmail(to, payload);
      writePending(null);
    } else {
      // Scout finished before the marketer saved an address — flush on setNotifyEmail.
      writePending(payload);
    }
  }
  return row;
}
