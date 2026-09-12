import "@testing-library/jest-dom/vitest";
import React from "react";
import { vi } from "vitest";

// Motion's jsdom animations leave duplicate DOM nodes; strip to plain elements.
vi.mock("motion/react", () => {
  const passthrough = ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement("div", props, children);
  return {
    motion: new Proxy(
      {},
      {
        get: () => passthrough,
      },
    ),
    AnimatePresence: ({ children }: { children?: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
  };
});
