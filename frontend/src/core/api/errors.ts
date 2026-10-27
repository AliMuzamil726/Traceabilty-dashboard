/** Mirrors the backend envelope: { error: { code, message, details } }. */
export interface ErrorBody {
  code: string;
  message: string;
  details: unknown;
}

export interface FieldError {
  field: string;
  location: string;
  message: string;
  type: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.details = body.details;
  }

  /** Per-field messages from a 422 response, keyed by field path. */
  get fieldErrors(): Record<string, string> {
    const fields = (this.details as { fields?: FieldError[] } | null)?.fields ?? [];
    return Object.fromEntries(fields.map((f) => [f.field, f.message]));
  }

  get isNetwork(): boolean {
    return this.code === 'network_error';
  }
}

export function isErrorBody(value: unknown): value is { error: ErrorBody } {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false;
  const error = (value as { error: unknown }).error;
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as ErrorBody).code === 'string' &&
    typeof (error as ErrorBody).message === 'string'
  );
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  const message = error instanceof Error ? error.message : 'Unexpected error.';
  return new ApiError(0, { code: 'client_error', message, details: null });
}

/** Human message for any thrown value. */
export function errorMessage(error: unknown): string {
  return toApiError(error).message;
}
