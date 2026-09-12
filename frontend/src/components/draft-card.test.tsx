import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("motion/react", () => {
  const passthrough = ({
    children,
    ...rest
  }: {
    children?: React.ReactNode;
    [key: string]: unknown;
  }) => React.createElement("div", rest, children);
  return {
    motion: {
      div: passthrough,
    },
  };
});

import { DraftCard } from "./draft-card";
import type { Draft } from "@/lib/types";

afterEach(() => {
  cleanup();
});

function makeDraft(overrides: Partial<Draft> = {}): Draft {
  return {
    id: "draft-1",
    digest_id: "digest-1",
    cluster_format: "meme",
    cluster_theme: "launch week",
    caption: "Ship loud, ship proud.",
    image_concept: "Neon product shot with lime accents",
    image_mime_type: null,
    image_data_base64: null,
    voice_examples_used: ["caption-a"],
    compliance_passed: true,
    compliance_rule_violations: [],
    compliance_llm_reason: "",
    review_state: "pending",
    edited_caption: null,
    final_caption: "Ship loud, ship proud.",
    created_at: "2026-09-10T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
    ...overrides,
  };
}

describe("DraftCard", () => {
  it("renders caption and approve/edit/reject actions for a pending draft", () => {
    render(
      <DraftCard
        draft={makeDraft()}
        index={0}
        onApprove={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("Ship loud, ship proud.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Edit" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("shows compliance flag and reason when the draft failed checks", () => {
    render(
      <DraftCard
        draft={makeDraft({
          compliance_passed: false,
          compliance_llm_reason: "Mimics a competitor claim.",
        })}
        index={0}
        onApprove={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("Compliance flagged")).toBeInTheDocument();
    expect(screen.getByText("Mimics a competitor claim.")).toBeInTheDocument();
  });

  it("calls onApprove when Approve is clicked", async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn().mockResolvedValue(undefined);

    render(
      <DraftCard
        draft={makeDraft()}
        index={0}
        onApprove={onApprove}
        onEdit={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(onApprove).toHaveBeenCalledWith("draft-1");
  });

  it("disables actions once a draft is ready to publish", () => {
    render(
      <DraftCard
        draft={makeDraft({ review_state: "ready_to_publish" })}
        index={0}
        onApprove={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Edit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  });
});
