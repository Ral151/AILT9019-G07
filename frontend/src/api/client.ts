import type { ApiError, ApiResponse, HealthResponse, SamplesResponse } from '../types/api';

export const MAX_MESSAGE_LENGTH = 500;

export class ApiRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiError;
    return body.detail ?? body.error;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function ask(message: string, signal?: AbortSignal): Promise<ApiResponse> {
  // Multipart, as specified in FR-7. The optional `image` field is added by
  // the photo flow (milestone M4).
  const form = new FormData();
  form.append('message', message);
  const res = await fetch('/api/ask', { method: 'POST', body: form, signal: signal ?? null });
  if (!res.ok) {
    throw new ApiRequestError(await readError(res), res.status);
  }
  return (await res.json()) as ApiResponse;
}

export async function getSamples(): Promise<string[]> {
  const res = await fetch('/api/samples');
  if (!res.ok) {
    throw new ApiRequestError(await readError(res), res.status);
  }
  const body = (await res.json()) as SamplesResponse;
  return body.samples;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch('/api/health');
  if (!res.ok) {
    throw new ApiRequestError(await readError(res), res.status);
  }
  return (await res.json()) as HealthResponse;
}
