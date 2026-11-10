"use client";

const TOKEN_KEY = "office_tools_access_token";
export const AUTH_TOKEN_CLEARED_EVENT = "office-tools:auth-token-cleared";

export function getToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  try {
    return window.sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(notify = true): void {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.removeItem(TOKEN_KEY);
  if (notify) {
    window.dispatchEvent(new Event(AUTH_TOKEN_CLEARED_EVENT));
  }
}
