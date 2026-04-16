export type RuntimeParserStatus = {
  parser_id: string;
  installed: boolean;
  enabled: boolean;
  reason: string | null;
};

export type RuntimeStatusResponse = {
  parsers: RuntimeParserStatus[];
};

export type HealthResponse = {
  service: string;
  status: string;
  api_version: string;
  llm_configured: boolean;
  azure_model: string;
};

export type S3ObjectOption = {
  label: string;
  bucket: string;
  key: string;
  s3_uri: string;
  document_format: string | null;
  size_bytes: number | null;
  updated_at: string | null;
};

export type S3ObjectListResponse = {
  objects: S3ObjectOption[];
};

export type S3BucketOption = {
  name: string;
  label: string;
};

export type S3BucketListResponse = {
  buckets: S3BucketOption[];
};

export type Excerpt = {
  label: string;
  content: string;
  mime_type: string;
  highlight_text: string | null;
  location_hint: string | null;
  metadata: Record<string, unknown>;
};

export type Issue = {
  issue_id: string;
  code: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
  stage: string;
  block_ref: string | null;
  excerpts: Excerpt[];
  metadata: Record<string, unknown>;
};

export type Artifact = {
  kind: string;
  label: string;
  path: string | null;
  metadata: Record<string, unknown>;
};

export type MarkdownLineMapEntry = {
  line_number: number;
  text: string;
  refs: string[];
  page_number?: number | null;
};

export type RepairCandidate = {
  issue_id: string;
  repair_type: string;
  strategy: string;
  origin: string;
  source_text: string;
  source_span: string | null;
  candidate_text: string | null;
  normalized_math: string | null;
  confidence: number;
  rationale: string;
  requires_review: boolean;
  llm_recommended: boolean;
  block_ref: string | null;
  markdown_line_number: number | null;
  location_hint: string | null;
  severity: string;
  patch_proposal: RepairPatchProposal | null;
};

export type RepairPatchProposal = {
  action: string;
  target_text: string;
  replacement_text: string;
  origin?: string | null;
  block_ref: string | null;
  location_hint: string | null;
  markdown_line_number: number | null;
  confidence: number;
  rationale: string;
  uncertain: boolean;
};

export type ResolutionIssueDetail = {
  issue_id: string;
  corruption_class: string | null;
  resolved: boolean;
  selected_origin: string | null;
  selected_confidence: number | null;
  selection_reason: string | null;
  llm_requested: boolean;
  llm_attempted: boolean;
  unresolved_reason: string | null;
  candidate_decisions: ResolutionCandidateDecision[];
};

export type ResolutionCandidateDecision = {
  candidate_index: number;
  origin: string;
  strategy: string | null;
  confidence: number;
  selected: boolean;
  patch_available: boolean;
  rejected_reason: string | null;
};

export type ResolutionSummary = {
  repair_issue_count: number;
  resolved_issue_count: number;
  recovered_deterministic_count: number;
  recovered_llm_count: number;
  unresolved_repair_issue_count: number;
  unresolved_by_class: Record<string, number>;
  unresolved_by_reason: Record<string, number>;
  issues: ResolutionIssueDetail[];
};

export type LlmDiagnostics = {
  routing_used: boolean;
  routing_recommendation: string | null;
  routing_baseline_parser: string | null;
  routing_selected_parser: string | null;
  routing_override_applied: boolean;
  routing_comparison_preview: string[];
  repair_attempted_issues: number;
  repair_generated_candidates: number;
  repair_error: string | null;
  repair_response_available: boolean;
  repair_response_preview: string[];
  formula_probe_attempted: boolean;
  formula_probe_error: string | null;
  formula_probe_apply_as_patch: boolean | null;
  formula_probe_confidence: number | null;
  formula_probe_region_image_path: string | null;
  formula_probe_preview: string[];
};

export type TraceEvent = {
  event_id: string;
  stage: string;
  kind: string;
  status: 'pending' | 'running' | 'succeeded' | 'degraded' | 'failed';
  timestamp: string;
  component: string;
  message: string;
  artifact: Artifact | null;
  issue: Issue | null;
  excerpts: Excerpt[];
  data: Record<string, unknown>;
};

export type ParseResponse = {
  request_id: string;
  source: {
    kind: string;
    name: string;
    uri: string | null;
    document_format: string;
    size_bytes: number;
    content_type: string | null;
  };
  routing: {
    level: string;
    primary_parser: string;
    fallback_parsers: string[];
    llm_usage: string;
    rationale: string[];
    policy_metadata: Record<string, unknown>;
  };
  handoff: {
    decision: 'accept' | 'degraded_accept' | 'hold';
    summary: string;
    reasons: string[];
    metadata: Record<string, string>;
  };
  trace: {
    trace_id: string;
    status: string;
    source: ParseResponse['source'];
    events: TraceEvent[];
    warnings: string[];
    metadata: Record<string, unknown>;
  };
  issues: Issue[];
  artifacts: Artifact[];
  markdown: string;
  markdown_line_map?: MarkdownLineMapEntry[];
  repair_candidates?: RepairCandidate[];
  suggested_resolved_markdown?: string | null;
  suggested_resolved_patches?: RepairPatchProposal[];
  final_resolved_markdown?: string | null;
  final_resolved_patches?: RepairPatchProposal[];
  resolution_summary: ResolutionSummary;
  llm_diagnostics: LlmDiagnostics;
  downstream_handoff: {
    policy: string;
    preferred_markdown_kind: string;
    review_required: boolean;
    source_markdown_available: boolean;
    suggested_resolved_available: boolean;
    final_resolved_available: boolean;
    rationale: string[];
  };
  evaluation: {
    readiness_score: number;
    readiness_label: string;
    issue_count: number;
    repair_candidate_count: number;
    deterministic_candidate_count: number;
    llm_candidate_count: number;
    suggested_patch_count: number;
    recovered_deterministic_count: number;
    recovered_llm_count: number;
    unresolved_repair_issue_count: number;
    review_required: boolean;
    recommended_next_step: string;
    rationale: string[];
  };
  llm_requested: boolean;
  llm_used: boolean;
  notes: string[];
};
