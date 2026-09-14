export type Cluster = {
  format: string;
  dominant_theme: string;
  post_count: number;
  total_engagement: number;
  avg_engagement: number;
  top_post_id: string;
  top_post_caption: string;
  account_ids: string[];
};

export type Digest = {
  id: string;
  generated_at: string;
  clusters: Cluster[];
  trending_themes: string[];
  gap_themes: string[];
  post_count: number;
};

export type ReviewState = "pending" | "edited" | "rejected" | "ready_to_publish";

export type RuleViolation = {
  rule: string;
  category: string;
  matched_text: string;
};

export type Draft = {
  id: string;
  digest_id: string;
  cluster_format: string;
  cluster_theme: string;
  caption: string;
  image_concept: string;
  image_mime_type: string | null;
  image_data_base64: string | null;
  voice_examples_used: string[];
  compliance_passed: boolean;
  compliance_rule_violations: RuleViolation[];
  compliance_llm_reason: string;
  review_state: ReviewState;
  edited_caption: string | null;
  final_caption: string;
  created_at: string;
  updated_at: string;
};

export type PipelineRunStatus = "pending" | "running" | "done" | "error";

export type PipelineRunCreated = {
  run_id: string;
  status: PipelineRunStatus;
};

export type PipelineRun = {
  id: string;
  status: PipelineRunStatus;
  digest_id: string | null;
  draft_ids: string[];
  error_detail: string | null;
  created_at: string;
};

export type IngestionRunStatus = "pending" | "running" | "done" | "error" | "cancelled";

export type IngestionTarget = {
  handle: string;
  platform: string;
  url?: string | null;
};

export type IngestionRunCreate = {
  connector: "fixture" | "social_profile" | "youtube" | "auto";
  targets: IngestionTarget[];
  record: boolean;
  headless?: boolean;
  lookback_days?: number;
  date_from?: string | null;
  date_to?: string | null;
};

export type IngestionRunCreated = {
  run_id: string;
  status: IngestionRunStatus;
};

export type IngestionRun = {
  id: string;
  connector_type: string;
  status: IngestionRunStatus;
  record: boolean;
  recording_key: string | null;
  error_detail: string | null;
  result: Record<string, unknown> | null;
  created_at: string;
};

export type CompetitorAccount = {
  id: string;
  handle: string;
  display_name: string;
  platform: string;
};

export type CommentSample = {
  author: string;
  text: string;
  likes: number;
};

export type CompetitorPost = {
  id: string;
  account_id: string;
  external_post_id: string;
  format: string;
  theme_tags: string;
  caption: string;
  image_url: string | null;
  likes: number;
  comments: number;
  shares: number;
  views?: number;
  media_urls?: string[];
  media_keys?: string[];
  comment_sample?: CommentSample[];
  posted_at: string;
  engagement_score: number;
  themes: string[];
};

export type AgentStepType =
  | "nav"
  | "action"
  | "screenshot"
  | "dom_snapshot"
  | "log"
  | "status"
  | "error"
  | "artifact";

export type AgentEvent = {
  run_id: string;
  agent_id: string;
  service: string;
  step_type: AgentStepType;
  payload: Record<string, unknown>;
  timestamp: string;
  sequence: number;
};

export type BrandProfile = {
  displayName: string;
  category: string;
  website: string;
  socials: {
    linkedin: string;
    x: string;
    instagram: string;
    tiktok: string;
    youtube: string;
    threads: string;
  };
  voiceNotes: string;
  forbiddenClaims: string;
  idealCustomer: string;
  contentPillars: string;
  preferredFormats: string[];
  timezone: string;
};

export type CompetitorProfile = {
  id: string;
  name: string;
  website: string;
  socials: BrandProfile["socials"];
  whyTheyMatter: string;
};

export type CreativePermissions = {
  draftReplies: boolean;
  draftTrendJack: boolean;
  suggestComments: boolean;
  imageConcepts: boolean;
  carouselOutlines: boolean;
  comparisonSlides: boolean;
};

export type ConnectionStatus = {
  platform: string;
  status: "connected" | "needs_reconnect" | "not_connected";
  auth_type?: string | null;
  expires_at?: string | null;
  scopes?: string[];
  detail?: string | null;
};

export type MissionState = {
  brand: BrandProfile;
  competitors: CompetitorProfile[];
  permissions: CreativePermissions;
  recordSession: boolean;
  lookbackDays: number;
  /** ISO date YYYY-MM-DD when custom range is active */
  dateFrom: string | null;
  dateTo: string | null;
  lastRunId: string | null;
};

export type CreativeKind = "image" | "comment" | "reply" | "studio";

export type CreativeRequest = {
  kind: CreativeKind;
  report_markdown?: string;
  brand_name: string;
  voice_notes?: string;
  competitor_caption?: string;
  forbidden_claims?: string;
  platform?: string;
  format?: string;
  spice?: number;
  tone?: string;
  post_url?: string;
  facts_json?: string;
  brand_category?: string;
  ideal_customer?: string;
  content_pillars?: string;
  preferred_formats?: string[];
  /** 1-based when generating a batch of studio frames / memes */
  variant?: number;
  variant_count?: number;
};

export type CreativeResult = {
  kind: CreativeKind;
  text: string;
  image_concept: string | null;
  image_mime_type: string | null;
  image_data_base64: string | null;
  image_error?: string | null;
  why_slaps?: string | null;
  overlay_text?: string | null;
  hashtags?: string[];
};

export type IntelPlay = {
  title: string;
  format: string;
  platform: string;
  why: string;
};

export type IntelSection = {
  id: string;
  title: string;
  markdown: string;
};

export type IntelReport = {
  scoreboard_blurb: string;
  markdown: string;
  reports: IntelSection[];
  good_at: string[];
  fumbling: string[];
  why_engagement_mid: string[];
  gaps: string[];
  plays: IntelPlay[];
  sniper_bait: { why: string; href: string; company: string }[];
  agents_used?: string[];
  narration?: "agent" | "fallback";
};

export type CommentDropResult = {
  ok: boolean;
  detail: string;
  screenshot_jpeg_b64?: string | null;
};
