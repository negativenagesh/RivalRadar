import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getNotifyEmail,
  loadNotifications,
  markAllNotificationsRead,
  pushNotification,
  setNotifyEmail,
  unreadCount,
} from "./notifications";

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("notifications", () => {
  it("stores in-app notifications and counts unread", () => {
    pushNotification({
      kind: "scout_done",
      title: "Scout finished — Pixis",
      body: "12 posts",
      href: "/mission",
      email: false,
    });
    const rows = loadNotifications();
    expect(rows).toHaveLength(1);
    expect(rows[0].title).toContain("Scout finished");
    expect(unreadCount()).toBe(1);
    markAllNotificationsRead();
    expect(unreadCount()).toBe(0);
  });

  it("saves notify email and posts to gateway for scout_done", async () => {
    setNotifyEmail("growth@pixis.example");
    expect(getNotifyEmail()).toBe("growth@pixis.example");
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    pushNotification({
      kind: "scout_done",
      title: "Scout finished — Pixis",
      body: "Ready",
      href: "/mission",
      email: true,
    });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][0]).toContain("/notify/email");
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.to).toBe("growth@pixis.example");
    expect(body.kind).toBe("scout_done");
  });
});
