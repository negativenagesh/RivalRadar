import { cleanup, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ServerStatusChip } from "./server-status-chip";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ServerStatusChip", () => {
  it("shows API online after health and ready succeed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/ready") || url.includes("/health")) {
          return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
        }
        return new Response("missing", { status: 404 });
      }),
    );

    render(<ServerStatusChip />);
    expect(screen.getByRole("status")).toHaveTextContent(/Checking API/i);
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/API online/i);
    });
  });
});
