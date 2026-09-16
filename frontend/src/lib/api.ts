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
import { loadOperatorState, resolveImageModel, resolveTextModel } from "./operator-models";

export const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";

export type ServerModelDefaults = {
  text_model: "gemini" | "deepseek" | "gptoss" | null;
  image_model: "nano_banana" | "agnes" | "nvidia_flux" | null;
  available: boolean;
  source: string;
};

export function getServerModelDefaults(): Promise<ServerModelDefaults> {
  return request<ServerModelDefaults>("/models/defaults");
}

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

async function request<T>(path: string, init?: RequestInit & { operator?: boolean }): Promise<T> {
  const { operator: attachOperator, ...rest } = init ?? {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string> | undefined),
  };
  if (attachOperator) {
    const state = loadOperatorState();
    const text = resolveTextModel(state);
    const image = resolveImageModel(state);
    if (state.gemini) headers["X-Gemini-Key"] = state.gemini;
    if (state.deepseek) headers["X-DeepSeek-Key"] = state.deepseek;
    if (state.nvidia) headers["X-Nvidia-Key"] = state.nvidia;
    if (state.agnes) headers["X-Agnes-Key"] = state.agnes;
    // Always send the operator's model preference — with no keys, the server
    // honors it via env keys (gpt-oss / Agnes defaults) when configured.
    headers["X-Text-Model"] = text ?? state.textModel;
    headers["X-Image-Model"] = image ?? state.imageModel;
  }
  const url = `${GATEWAY_URL}${path}`;
  let response: Response | undefined;
  let lastErr: unknown;
  // One retry after short wait — Render free tier cold starts often drop the first fetch.
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      response = await fetch(url, {
        ...rest,
        headers,
        cache: "no-store",
      });
      lastErr = undefined;
      break;
    } catch (err) {
      lastErr = err;
      if (attempt === 0) {
        await new Promise((r) => setTimeout(r, 2500));
        continue;
      }
    }
  }
  if (!response) {
    const reason = lastErr instanceof Error ? lastErr.message : "network error";
    throw new Error(
      `Gateway unreachable (${reason}). Is it running at ${GATEWAY_URL}? ` +
        `If Start Scout fails, wait for Render wake (/ready shows ingestion=ok) then retry.`,
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
    operator: true,
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
    operator: true,
  });
}

export type PublishVariation = {
  caption: string;
  hashtags: string[];
  title: string;
  description: string;
  why: string;
};

export type PublishPlan = {
  platform: string;
  agent: string;
  variations: PublishVariation[];
};


export type PublishStreamEvent =
  | { event: "stage"; agent: string; status: "writing" }
  | { event: "delta"; agent: string; text: string }
  | { event: "plan"; plan: PublishPlan }
  | { event: "error"; detail: string };

export async function streamPublishPlan(
  body: {
    brand_name: string;
    platform: string;
    asset_caption: string;
    overlay_text?: string;
    asset_context?: string;
    image_concept?: string;
    intel_markdown?: string;
    facts_json?: string;
    format?: string;
    spice?: number;
    variations?: number;
  },
  onEvent?: (event: PublishStreamEvent) => void,
): Promise<PublishPlan> {
  const events = await readSseStream<PublishStreamEvent>(
    "/creative/publish-plan/stream",
    body,
    onEvent,
  );
  const planEvent = events.find((e): e is Extract<PublishStreamEvent, { event: "plan" }> => e.event === "plan");
  if (!planEvent) throw new Error("Publish stream ended without a plan.");
  return planEvent.plan;
}

export type CommentStreamEvent =
  | { event: "stage"; agent: string; status: "writing" }
  | { event: "delta"; agent: string; text: string }
  | { event: "result"; result: CreativeResult }
  | { event: "error"; detail: string };

export async function streamCommentDraft(
  body: CreativeRequest,
  onEvent?: (event: CommentStreamEvent) => void,
): Promise<CreativeResult> {
  const events = await readSseStream<CommentStreamEvent>(
    "/creative/comment/stream",
    body,
    onEvent,
  );
  const resultEvent = events.find(
    (e): e is Extract<CommentStreamEvent, { event: "result" }> => e.event === "result",
  );
  if (!resultEvent) throw new Error("Comment stream ended without a result.");
  return resultEvent.result;
}

export function generatePublishPlan(body: {
  brand_name: string;
  platform: string;
  asset_caption: string;
  overlay_text?: string;
  asset_context?: string;
  image_concept?: string;
  intel_markdown?: string;
  facts_json?: string;
  format?: string;
  spice?: number;
  variations?: number;
}): Promise<PublishPlan> {
  return request<PublishPlan>("/creative/publish-plan", {
    method: "POST",
    body: JSON.stringify(body),
    operator: true,
  });
}

export type StagePostResult = {
  ok: boolean;
  detail: string;
  screenshot_jpeg_b64: string | null;
};

export function stagePlatformPost(body: {
  platform: string;
  caption: string;
  media_png_b64?: string;
  approved: boolean;
}): Promise<StagePostResult> {
  return request<StagePostResult>("/social/stage-post", {
    method: "POST",
    body: JSON.stringify(body),
  });
}


function operatorFetchHeaders(): Record<string, string> {
  const state = loadOperatorState();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (state.gemini) headers["X-Gemini-Key"] = state.gemini;
  if (state.deepseek) headers["X-DeepSeek-Key"] = state.deepseek;
  if (state.nvidia) headers["X-Nvidia-Key"] = state.nvidia;
  if (state.agnes) headers["X-Agnes-Key"] = state.agnes;
  headers["X-Text-Model"] = resolveTextModel(state) ?? state.textModel;
  headers["X-Image-Model"] = resolveImageModel(state) ?? state.imageModel;
  return headers;
}

async function readSseStream<TEvent extends { event: string }>(
  path: string,
  body: unknown,
  onEvent?: (event: TEvent) => void,
): Promise<TEvent[]> {
  let response: Response;
  try {
    response = await fetch(`${GATEWAY_URL}${path}`, {
      method: "POST",
      headers: operatorFetchHeaders(),
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : "network error";
    throw new Error(`Gateway unreachable (${reason}).`);
  }
  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const events: TEvent[] = [];
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const eventMatch = block.match(/^event: (.+)$/m);
      const dataMatch = block.match(/^data: (.+)$/m);
      if (!eventMatch || !dataMatch) continue;
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(dataMatch[1]) as Record<string, unknown>;
      } catch {
        continue;
      }
      const event = { event: eventMatch[1], ...data } as TEvent;
      if ((event as { event: string }).event === "error") {
        const detail = String((data as { detail?: string }).detail || "stream error");
        throw new Error(detail);
      }
      events.push(event);
      onEvent?.(event);
    }
  }
  return events;
}

export type IntelStreamEvent =
  | { event: "stage"; agent: string; status: "writing" }
  | { event: "agent"; agent: string; status: "done"; ok: boolean }
  | { event: "delta"; agent: string; markdown: string; replace?: boolean }
  | { event: "report"; report: IntelReport }
  | { event: "error"; detail: string };

/** SSE intel stream: per-agent progress events, resolves with the final report. */
export async function streamIntelReport(
  body: {
    facts: unknown;
    brand_name: string;
    voice_notes?: string;
    forbidden_claims?: string;
  },
  onEvent?: (event: IntelStreamEvent) => void,
): Promise<IntelReport> {
  const state = loadOperatorState();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (state.gemini) headers["X-Gemini-Key"] = state.gemini;
  if (state.deepseek) headers["X-DeepSeek-Key"] = state.deepseek;
  if (state.nvidia) headers["X-Nvidia-Key"] = state.nvidia;
  if (state.agnes) headers["X-Agnes-Key"] = state.agnes;
  headers["X-Text-Model"] = resolveTextModel(state) ?? state.textModel;
  headers["X-Image-Model"] = resolveImageModel(state) ?? state.imageModel;

  let response: Response;
  try {
    response = await fetch(`${GATEWAY_URL}/intel/report/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : "network error";
    throw new Error(`Gateway unreachable (${reason}).`);
  }
  if (!response.ok || !response.body) {
    throw new Error(`Intel stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let report: IntelReport | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const eventMatch = block.match(/^event: (.+)$/m);
      const dataMatch = block.match(/^data: (.+)$/m);
      if (!eventMatch || !dataMatch) continue;
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(dataMatch[1]) as Record<string, unknown>;
      } catch {
        continue;
      }
      const event = { event: eventMatch[1], ...data } as IntelStreamEvent;
      if (event.event === "error") {
        throw new Error(event.detail || "Intel stream error");
      }
      if (event.event === "report") {
        report = event.report;
      }
      onEvent?.(event);
    }
  }
  if (!report) throw new Error("Intel stream ended without a report.");
  return report;
}

export function pingLlm(
  vendor: "gemini" | "deepseek" | "nvidia" | "agnes",
  apiKey: string,
): Promise<{ vendor: string; model: string; preview: string }> {
  const headers: Record<string, string> = {};
  if (vendor === "gemini") headers["X-Gemini-Key"] = apiKey;
  if (vendor === "deepseek") headers["X-DeepSeek-Key"] = apiKey;
  if (vendor === "nvidia") headers["X-Nvidia-Key"] = apiKey;
  if (vendor === "agnes") headers["X-Agnes-Key"] = apiKey;
  return request("/llm/ping", {
    method: "POST",
    body: JSON.stringify({ vendor }),
    headers,
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

export type PairingCode = {
  code: string;
  expires_in: number;
  workspace_id: string;
};

export function createPairingCode(workspaceId = "default"): Promise<PairingCode> {
  return request<PairingCode>("/connect/pairing", {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId }),
  });
}

export function ingestionMediaUrl(mediaKey: string): string {
  return `${GATEWAY_URL}/ingestion/media/${mediaKey}`;
}
