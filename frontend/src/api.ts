import type {
  HealthResponse,
  ParseResponse,
  RuntimeStatusResponse,
  S3BucketListResponse,
  S3ObjectListResponse,
} from './types';

const rawApiBase = (import.meta.env.VITE_MARKBRIDGE_API_BASE as string | undefined)?.trim();
const API_BASE = rawApiBase ? rawApiBase.replace(/\/$/, '') : '';

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getApiBase(): string {
  return API_BASE;
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health');
}

export function fetchRuntimeStatus(): Promise<RuntimeStatusResponse> {
  return requestJson<RuntimeStatusResponse>('/v1/runtime-status');
}

export function fetchS3Buckets(): Promise<S3BucketListResponse> {
  return requestJson<S3BucketListResponse>('/v1/s3/buckets');
}

export function fetchS3Objects(params: { bucket: string; prefix?: string; limit?: number }): Promise<S3ObjectListResponse> {
  const search = new URLSearchParams({
    bucket: params.bucket,
    prefix: params.prefix || '',
    limit: String(params.limit || 100),
  });
  return requestJson<S3ObjectListResponse>(`/v1/s3/objects?${search.toString()}`);
}

export function parseS3(body: {
  s3_uri: string;
  llm_requested: boolean;
  parser_hint?: string | null;
}): Promise<ParseResponse> {
  return requestJson<ParseResponse>('/v1/parse/s3', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
}

export function parseUpload(input: {
  file: File;
  llmRequested: boolean;
  parserHint?: string | null;
}): Promise<ParseResponse> {
  const formData = new FormData();
  formData.append('file', input.file);
  formData.append('llm_requested', String(input.llmRequested));
  if (input.parserHint) {
    formData.append('parser_hint', input.parserHint);
  }
  return requestJson<ParseResponse>('/v1/parse/upload', {
    method: 'POST',
    body: formData,
  });
}
