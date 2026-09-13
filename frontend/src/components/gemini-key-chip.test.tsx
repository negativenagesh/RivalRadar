import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { GeminiKeyChip } from "./gemini-key-chip";
import { GeminiKeyProvider } from "./gemini-key-provider";
import { GEMINI_KEY_EVENT, GEMINI_KEY_STORAGE } from "@/lib/gemini-key";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe("GeminiKeyChip", () => {
  it("pulses until a key exists then shows last-4", async () => {
    render(
      <GeminiKeyProvider>
        <GeminiKeyChip />
      </GeminiKeyProvider>,
    );
    const missing = await screen.findByRole("button", { name: /^Gemini$/i });
    expect(missing.className).toContain("animate-pulse");

    window.localStorage.setItem(GEMINI_KEY_STORAGE, "AIzaSyDummyKey1234");
    window.dispatchEvent(new Event(GEMINI_KEY_EVENT));

    const ready = await screen.findByRole("button", { name: /Gemini ••••1234/ });
    expect(ready.className).not.toContain("animate-pulse");
  });

  it("portals the key sheet onto the viewport, not the sticky navbar", async () => {
    const user = userEvent.setup();
    render(
      <GeminiKeyProvider>
        <header className="sticky top-0 z-50 backdrop-blur-md" data-testid="nav-shell">
          <GeminiKeyChip />
        </header>
      </GeminiKeyProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /^Gemini$/i }));

    const dialog = await screen.findByRole("dialog", { name: /Gemini API key/i });
    expect(dialog.closest("[data-testid='nav-shell']")).toBeNull();
    expect(dialog.parentElement).toHaveAttribute("data-testid", "gemini-key-overlay");
    expect(dialog.parentElement?.className).toMatch(/fixed/);
    expect(dialog.parentElement?.className).toMatch(/inset-0/);
    expect(dialog.parentElement?.className).toMatch(/place-items-center/);
    expect(document.body.contains(dialog)).toBe(true);
  });
});
