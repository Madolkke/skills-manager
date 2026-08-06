import { getActorId } from "../identity";

export type ApiBaseUrlInput = {
  configuredUrl?: string;
  configuredPort?: string;
  location?: Pick<Location, "protocol" | "hostname">;
};

export type RequestOptions = { admin?: boolean; signal?: AbortSignal };

export function resolveApiBaseUrl({ configuredUrl, configuredPort, location }: ApiBaseUrlInput): string {
  const explicitUrl = configuredUrl?.trim();
  if (explicitUrl) return explicitUrl.replace(/\/+$/, "");

  const port = configuredPort?.trim() || "8000";
  const protocol = location?.protocol === "https:" ? "https:" : "http:";
  const hostname = location?.hostname || "127.0.0.1";
  return `${protocol}//${hostname}:${port}`;
}

export const API_BASE_URL = resolveApiBaseUrl({
  configuredUrl: import.meta.env.VITE_SKILLHUB_API_URL,
  configuredPort: import.meta.env.VITE_SKILLHUB_API_PORT,
  location: typeof window === "undefined" ? undefined : window.location,
});

export class ApiError extends Error {
  readonly fieldErrors: Record<string, string>;
  readonly status: number;

  constructor(message: string, status: number, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

export function apiErrorMessage(error: ApiError): string {
  const messages = Object.values(error.fieldErrors).filter(Boolean);
  return messages.length ? messages.join("；") : error.message;
}

export async function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: requestHeaders(options),
    signal: options.signal,
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json() as Promise<T>;
}

export async function apiSend<T>(path: string, method: "POST" | "PATCH" | "PUT", body: unknown, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: requestHeaders({ ...options, json: true }),
    body: JSON.stringify(body),
    signal: options.signal,
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json() as Promise<T>;
}

export async function apiDelete<T>(path: string, options: RequestOptions = {}, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    credentials: "include",
    headers: requestHeaders({ ...options, json: body !== undefined }),
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: options.signal,
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json() as Promise<T>;
}

export async function apiDownload(path: string, options: RequestOptions = {}): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: requestHeaders(options),
    signal: options.signal,
  });
  if (!response.ok) throw await parseApiError(response);
  return response.blob();
}

export async function apiDownloadBase64(path: string, options: RequestOptions = {}): Promise<string> {
  return blobToBase64(await apiDownload(path, options));
}

function requestHeaders(options: RequestOptions & { json?: boolean } = {}): HeadersInit {
  const headers: Record<string, string> = { accept: "application/json", "X-SkillHub-Actor": getActorId() };
  if (options.json) headers["content-type"] = "application/json";
  if (options.admin) {
    const key = typeof window === "undefined" ? "" : window.sessionStorage.getItem("skillhub.admin.key") || "";
    if (key) headers["X-SkillHub-Admin-Key"] = key;
  }
  return headers;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("读取 artifact 失败。"));
    reader.readAsDataURL(blob);
  });
}

async function parseApiError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      field_errors?: Record<string, string> | Array<{ field?: string; message?: string }>;
    };
    const message = typeof payload.detail === "string" ? payload.detail : `${response.status} ${response.statusText}`;
    const error = new ApiError(message, response.status, normalizeFieldErrors(payload.field_errors));
    return new ApiError(apiErrorMessage(error), response.status, error.fieldErrors);
  } catch {
    return new ApiError(`${response.status} ${response.statusText}`, response.status);
  }
}

function normalizeFieldErrors(errors: unknown): Record<string, string> {
  if (!errors) return {};
  if (!Array.isArray(errors)) return errors as Record<string, string>;
  return Object.fromEntries(errors.map((item) => {
    const row = item as { field?: unknown; message?: unknown };
    return [typeof row.field === "string" ? row.field : "_form", String(row.message ?? "字段格式不正确。")];
  }));
}
