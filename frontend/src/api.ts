import type { Board } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  getBoard: () => request<Board>("/api/board"),
  syncNow: () =>
    request<{ ok: boolean; total: number; counts: Record<string, number>; synced_at: string }>(
      "/api/sync/now",
      { method: "POST" }
    ),
  syncStatus: () =>
    request<{ synced_at: string | null; counts: Record<string, number>; watching: boolean }>(
      "/api/sync/status"
    ),
  hideProject: (path: string) =>
    request<{ paths: string[] }>("/api/projects/hide", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  unhideProject: (path: string) =>
    request<{ paths: string[] }>("/api/projects/unhide", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
};
