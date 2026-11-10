"use client";

import { ApiError } from "@/lib/errors";
import { clearToken, getToken } from "@/lib/auth-storage";
import type {
  ApiErrorBody,
  ApiSuccess,
  AuthUser,
  LoginResult,
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
