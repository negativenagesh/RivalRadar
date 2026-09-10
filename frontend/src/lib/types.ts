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
