"use client";

import { ApiError } from "@/lib/errors";
import { clearToken, getToken } from "@/lib/auth-storage";
import type {
  AuditLogItem,
  ApiErrorBody,
  ApiSuccess,
  AuthUser,
  HistoryItem,
  LoginResult,
  PaginatedItems,
  RuntimeErrorItem,
} from "@/lib/types";

type RegisterPayload = {
  username: string;
  password: string;
  recovery_question: string;
  recovery_answer: string;
};

type ResetPasswordPayload = {
  username: string;
  recovery_question: string;
  recovery_answer: string;
  new_password: string;
};

type ChangePasswordPayload = {
  current_password: string;
  new_password: string;
};

async function readJson<T>(response: Response): Promise<T> {
  let body: ApiSuccess<T> | ApiErrorBody;
  try {
    body = (await response.json()) as ApiSuccess<T> | ApiErrorBody;
  } catch {
    throw new ApiError("服务器返回了无法识别的内容", "INVALID_RESPONSE", response.status);
  }
  if (!response.ok || !body.success) {
    const error = body.success ? null : body.error;
    throw new ApiError(
      error?.message ?? "请求失败，请稍后重试",
      error?.code ?? "REQUEST_FAILED",
      response.status,
      error?.details,
    );
  }
  return body.data;
}

async function throwResponseError(response: Response): Promise<never> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    throw new ApiError(
      body.error?.message ?? "请求失败，请稍后重试",
      body.error?.code ?? "REQUEST_FAILED",
      response.status,
      body.error?.details,
    );
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("请求失败，请稍后重试", "REQUEST_FAILED", response.status);
  }
}

export async function authenticatedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) {
    clearToken();
  }
  return response;
}

export async function registerAccount(payload: RegisterPayload): Promise<AuthUser> {
  return readJson<AuthUser>(
    await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function loginAccount(username: string, password: string): Promise<LoginResult> {
  return readJson<LoginResult>(
    await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  );
}

export async function logoutAccount(): Promise<void> {
  await readJson<null>(
    await authenticatedFetch("/api/v1/auth/logout", {
      method: "POST",
    }),
  );
}

export async function getCurrentUser(): Promise<AuthUser> {
  return readJson<AuthUser>(await authenticatedFetch("/api/v1/auth/me"));
}

export async function getRecoveryQuestion(username: string): Promise<string> {
  const data = await readJson<{ recovery_question: string }>(
    await fetch("/api/v1/auth/recovery-question", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    }),
  );
  return data.recovery_question;
}

export async function resetPassword(payload: ResetPasswordPayload): Promise<void> {
  await readJson<null>(
    await fetch("/api/v1/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function changePassword(payload: ChangePasswordPayload): Promise<string> {
  const data = await readJson<{ access_token: string }>(
    await authenticatedFetch("/api/v1/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
  return data.access_token;
}

export async function listHistory(): Promise<HistoryItem[]> {
  const data = await readJson<{ items: HistoryItem[] }>(
    await authenticatedFetch("/api/v1/history"),
  );
  return data.items;
}

export async function downloadHistoryFile(historyId: string): Promise<Blob> {
  const response = await authenticatedFetch(
    `/api/v1/history/${encodeURIComponent(historyId)}/download`,
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  return response.blob();
}

function withQuery(
  path: string,
  params: Record<string, string | number | undefined | null>,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

async function readAuthenticatedBlob(path: string): Promise<Blob> {
  const response = await authenticatedFetch(path);
  if (!response.ok) {
    return throwResponseError(response);
  }
  return response.blob();
}

export async function listAdminUsers(): Promise<AuthUser[]> {
  const data = await readJson<{ items: AuthUser[] }>(
    await authenticatedFetch("/api/v1/admin/users"),
  );
  return data.items;
}

export async function setAdminUserStatus(userId: number, isActive: boolean): Promise<AuthUser> {
  return readJson<AuthUser>(
    await authenticatedFetch(`/api/v1/admin/users/${userId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive }),
    }),
  );
}

export async function setAdminUserRole(
  userId: number,
  role: "user" | "admin",
): Promise<AuthUser> {
  return readJson<AuthUser>(
    await authenticatedFetch(`/api/v1/admin/users/${userId}/role`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    }),
  );
}

export async function forceAdminUserLogout(userId: number): Promise<AuthUser> {
  return readJson<AuthUser>(
    await authenticatedFetch(`/api/v1/admin/users/${userId}/logout`, {
      method: "POST",
    }),
  );
}

export async function resetAdminUserPassword(
  userId: number,
): Promise<{ temporary_password: string; user: AuthUser }> {
  return readJson<{ temporary_password: string; user: AuthUser }>(
    await authenticatedFetch(`/api/v1/admin/users/${userId}/reset-password`, {
      method: "POST",
    }),
  );
}

export type AuditLogFilters = {
  date?: string;
  event?: string;
  outcome?: "success" | "failure" | "";
  request_id?: string;
  username?: string;
  page?: number;
  page_size?: number;
};

export async function listAuditLogs(
  filters: AuditLogFilters,
): Promise<PaginatedItems<AuditLogItem>> {
  return readJson<PaginatedItems<AuditLogItem>>(
    await authenticatedFetch(withQuery("/api/v1/admin/audit-logs", filters)),
  );
}

export async function downloadAuditLogs(
  filters: AuditLogFilters,
  format: "csv" | "json",
): Promise<Blob> {
  return readAuthenticatedBlob(
    withQuery("/api/v1/admin/audit-logs/download", {
      date: filters.date,
      event: filters.event,
      outcome: filters.outcome,
      request_id: filters.request_id,
      username: filters.username,
      format,
    }),
  );
}

export async function listRuntimeErrors(
  date: string,
  page = 1,
  pageSize = 50,
): Promise<PaginatedItems<RuntimeErrorItem> & { date: string }> {
  return readJson<PaginatedItems<RuntimeErrorItem> & { date: string }>(
    await authenticatedFetch(
      withQuery("/api/v1/admin/runtime-errors", {
        date,
        page,
        page_size: pageSize,
      }),
    ),
  );
}

export async function downloadRuntimeErrors(date: string): Promise<Blob> {
  return readAuthenticatedBlob(
    withQuery("/api/v1/admin/runtime-errors/download", { date }),
  );
}
