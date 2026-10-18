// Mirrors backend/app/schemas (FR-7 response contract). Keep the two in sync.

export type Action = 'answer' | 'answer_with_caveat' | 'defer' | 'refuse';

export type ReasonCode =
  | 'OK'
  | 'OUT_OF_SCOPE_LOCATION'
  | 'OUT_OF_SCOPE_PENALTY'
  | 'OUT_OF_SCOPE_APPLICATION'
  | 'OUT_OF_SCOPE_OFFTOPIC'
  | 'ONSITE_SIGN_CONFLICT'
  | 'HAZARDOUS_OFFICIAL_LINKS_ONLY'
  | 'NO_UNIFIED_STANDARD'
  | 'LOW_RETRIEVAL_MATCH'
  | 'LOW_IMAGE_CONFIDENCE'
  | 'IMAGE_UNREADABLE'
  | 'MULTIPLE_ITEMS'
  | 'VALIDATION_FAILED'
  | 'SERVICE_UNAVAILABLE';

export interface Citation {
  source_id: string;
  title: string;
  section: string;
  lines: string;
  excerpt: string;
  url: string;
  retrieved_at: string;
}

export interface Redirect {
  label: string;
  url: string;
}

export interface ImageInfo {
  item_label: string;
  confidence: number;
  needs_clearer_input: boolean;
}

export interface ApiResponse {
  request_id: string;
  action: Action;
  reason_code: ReasonCode;
  answer_text: string;
  bin_category: string | null;
  caveats: string[];
  citations: Citation[];
  redirect: Redirect | null;
  image: ImageInfo | null;
  served_from_cache: boolean;
}

export interface ApiError {
  error: string;
  detail?: string;
}

export interface SamplesResponse {
  samples: string[];
}

// GET /api/health (only the fields the UI uses).
export interface HealthResponse {
  status: string;
  corpus_version: string;
  corpus_chunks: number;
  text_provider: string;
  text_model: string | null;
  text_provider_reachable: boolean | null;
  demo_cache: string;
  demo_cache_entries: number;
}
