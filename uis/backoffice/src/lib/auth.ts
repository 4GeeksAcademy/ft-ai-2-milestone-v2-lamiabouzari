import { useSyncExternalStore } from "react";
import { apiRequest } from "@/lib/api-client";

const TOKEN_STORAGE_KEY = "backoffice_access_token";

type Listener = () => void;
const listeners = new Set<Listener>();
// Stay false until after hydration so a stored token does not disagree with the server HTML.
let clientSnapshotReady = false;

function notifyAuthChange(): void {
  listeners.forEach((listener) => listener());
}

/** Subscribe to auth token changes (used by useSyncExternalStore). */
export function subscribeToAuthChanges(listener: Listener): () => void {
  listeners.add(listener);
  queueMicrotask(() => {
    if (!listeners.has(listener)) return;
    clientSnapshotReady = true;
    listener();
  });
  return () => listeners.delete(listener);
}


export interface AuthUser {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
  is_active: boolean;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  notifyAuthChange();
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  notifyAuthChange();
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const response = await apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
  setToken(response.access_token);
  return response.user;
}

export function logout(): void {
  clearToken();
}

function getAuthenticatedSnapshot(): boolean {
  return clientSnapshotReady && isAuthenticated();
}

function getServerAuthSnapshot(): boolean {
  return false;
}

/** Reactive auth flag backed by localStorage, safe for SSR/hydration. */
export function useIsAuthenticated(): boolean {
  return useSyncExternalStore(subscribeToAuthChanges, getAuthenticatedSnapshot, getServerAuthSnapshot);
}
