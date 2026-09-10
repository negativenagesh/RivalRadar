import type { Digest, Draft, PipelineRun, PipelineRunCreated } from "./types";

const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${GATEWAY_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getLatestDigest(): Promise<Digest> {
  return request<Digest>("/digest/latest");
}

export function generateDigest(): Promise<Digest> {
  return request<Digest>("/digest/generate", { method: "POST" });
}

export function generateDrafts(): Promise<PipelineRunCreated> {
  return request<PipelineRunCreated>("/drafts/generate", { method: "POST" });
}

export function getPipelineRun(runId: string): Promise<PipelineRun> {
  return request<PipelineRun>(`/pipeline-runs/${runId}`);
}

export function listDrafts(): Promise<Draft[]> {
  return request<Draft[]>("/drafts");
}

export function approveDraft(draftId: string): Promise<Draft> {
  return request<Draft>(`/drafts/${draftId}/approve`, { method: "POST" });
}

export function editDraft(draftId: string, caption: string): Promise<Draft> {
  return request<Draft>(`/drafts/${draftId}/edit`, {
    method: "POST",
    body: JSON.stringify({ caption }),
  });
}

export function rejectDraft(draftId: string): Promise<Draft> {
  return request<Draft>(`/drafts/${draftId}/reject`, { method: "POST" });
}
