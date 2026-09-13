import type {
  CommentDropResult,
  CompetitorAccount,
  CompetitorPost,
  ConnectionStatus,
  CreativeRequest,
  CreativeResult,
  Digest,
  Draft,
  IngestionRun,
  IngestionRunCreate,
  IngestionRunCreated,
  IntelReport,
  PipelineRun,
  PipelineRunCreated,
} from "./types";
import { loadGeminiKey } from "./gemini-key";

export const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";

function errorDetail(body: { detail?: unknown }, fallback: string): string {
  const detail = body.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) return String((item as { msg: unknown }).msg);
        return "";
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit & { gemini?: boolean }): Promise<T> {
  const { gemini: attachGemini, ...rest } = init ?? {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string> | undefined),
  };
  if (attachGemini) {
    const gemini = loadGeminiKey();
    if (gemini) headers["X-Gemini-Key"] = gemini;
  }
  let response: Response;
  try {
    response = await fetch(`${GATEWAY_URL}${path}`, {
      ...rest,
      headers,
      cache: "no-store",
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : "network error";
    throw new Error(
      `Gateway unreachable (${reason}). Is it running at ${GATEWAY_URL}? Rebuild gateway + generation if /intel/report 404s.`,
    );
  }
  if (!response.ok) {
    let detail = `${init?.method ?? "GET"} ${path} failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = errorDetail(body, detail);
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
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

export function startIngestionRun(body: IngestionRunCreate): Promise<IngestionRunCreated> {
  return request<IngestionRunCreated>("/ingestion/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getIngestionRun(runId: string): Promise<IngestionRun> {
  return request<IngestionRun>(`/ingestion/runs/${runId}`);
}

export function cancelIngestionRun(runId: string): Promise<IngestionRun> {
  return request<IngestionRun>(`/ingestion/runs/${runId}/cancel`, { method: "POST" });
}

export function listIngestionPosts(): Promise<CompetitorPost[]> {
  return request<CompetitorPost[]>("/ingestion/posts");
}

export function listIngestionAccounts(): Promise<CompetitorAccount[]> {
  return request<CompetitorAccount[]>("/ingestion/accounts");
}

export function ingestionRecordingUrl(runId: string): string {
  return `${GATEWAY_URL}/ingestion/runs/${runId}/recording`;
}

export function ingestionScreenshotUrl(runId: string, index: number): string {
  return `${GATEWAY_URL}/ingestion/runs/${runId}/screenshots/${index}`;
}

export function ingestionLiveWsUrl(runId: string): string {
  const base = GATEWAY_URL.replace(/^http/, "ws");
  return `${base}/ingestion/runs/${runId}/live`;
}

export function generateCreative(body: CreativeRequest): Promise<CreativeResult> {
  return request<CreativeResult>("/creative/generate", {
    method: "POST",
    body: JSON.stringify(body),
    gemini: true,
  });
}

export function generateIntelReport(body: {
  facts: unknown;
  brand_name: string;
  voice_notes?: string;
  forbidden_claims?: string;
}): Promise<IntelReport> {
  return request<IntelReport>("/intel/report", {
    method: "POST",
    body: JSON.stringify(body),
    gemini: true,
  });
}

export function dropSocialComment(body: {
  platform: string;
  url: string;
  text: string;
  approved: boolean;
}): Promise<CommentDropResult> {
  return request<CommentDropResult>("/social/comment", {
    method: "POST",
    body: JSON.stringify(body),
  });
}


export function listConnections(workspaceId = "default"): Promise<ConnectionStatus[]> {
  return request<ConnectionStatus[]>(`/connections?workspace_id=${encodeURIComponent(workspaceId)}`);
}

export function upsertConnection(
  platform: string,
  body: {
    auth_type: "oauth" | "cookie" | "api_key";
    secret: Record<string, unknown>;
    expires_at?: string | null;
    scopes?: string[];
    workspace_id?: string;
  },
): Promise<ConnectionStatus> {
  return request<ConnectionStatus>(`/connections/${platform}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteConnection(platform: string, workspaceId = "default"): Promise<void> {
  return request<void>(`/connections/${platform}?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: "DELETE",
  });
}

export type ConnectSession = {
  session_id: string;
  platform: string;
  status: "awaiting_login" | "ready" | "completed" | "cancelled" | "expired" | "error";
  login_url: string;
  detail?: string | null;
  agent_online?: boolean;
  viewer_url?: string | null;
};

export function startConnectSession(
  platform: string,
  workspaceId = "default",
): Promise<ConnectSession> {
  return request<ConnectSession>(`/connections/${platform}/sessions`, {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId }),
  });
}

export function getConnectSession(platform: string, sessionId: string): Promise<ConnectSession> {
  return request<ConnectSession>(`/connections/${platform}/sessions/${sessionId}`);
}

export function completeConnectSession(
  platform: string,
  sessionId: string,
): Promise<ConnectionStatus> {
  return request<ConnectionStatus>(`/connections/${platform}/sessions/${sessionId}/complete`, {
    method: "POST",
  });
}

export function cancelConnectSession(platform: string, sessionId: string): Promise<void> {
  return request<void>(`/connections/${platform}/sessions/${sessionId}/cancel`, {
    method: "POST",
  });
}

export function ingestionMediaUrl(mediaKey: string): string {
  return `${GATEWAY_URL}/ingestion/media/${mediaKey}`;
}
