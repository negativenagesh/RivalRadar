import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { GeminiKeyChip } from "./gemini-key-chip";
import { OperatorModelsProvider } from "./operator-models-provider";
import { OPERATOR_EVENT } from "@/lib/operator-models";
import { GEMINI_KEY_STORAGE } from "@/lib/gemini-key";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe("Models chip", () => {
  it("pulses until a key exists then shows last-4", async () => {
    render(
      <OperatorModelsProvider>
        <GeminiKeyChip />
      </OperatorModelsProvider>,
    );
    const missing = await screen.findByRole("button", { name: /^Models$/i });
    expect(missing.className).toContain("animate-pulse");

    window.localStorage.setItem(GEMINI_KEY_STORAGE, "AIzaSyDummyKey1234");
    window.dispatchEvent(new Event(OPERATOR_EVENT));

    const ready = await screen.findByRole("button", { name: /Gemini ••••1234/ });
    expect(ready.className).not.toContain("animate-pulse");
  });

  it("portals the key sheet onto the viewport, not the sticky navbar", async () => {
    const user = userEvent.setup();
    render(
      <OperatorModelsProvider>
        <header className="sticky top-0 z-50 backdrop-blur-md" data-testid="nav-shell">
          <GeminiKeyChip />
        </header>
      </OperatorModelsProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /^Models$/i }));

    const dialog = await screen.findByRole("dialog", { name: /^Models$/i });
    expect(dialog.closest("[data-testid='nav-shell']")).toBeNull();
    expect(dialog.parentElement).toHaveAttribute("data-testid", "gemini-key-overlay");
    expect(dialog.parentElement?.className).toMatch(/fixed/);
    expect(dialog.parentElement?.className).toMatch(/inset-0/);
    expect(dialog.parentElement?.className).toMatch(/place-items-center/);
    expect(document.body.contains(dialog)).toBe(true);
  });
});
