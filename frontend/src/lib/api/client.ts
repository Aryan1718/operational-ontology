import { appConfig } from "@/lib/config";
import type { ApiSuccessEnvelope } from "@/lib/api/types";

type RequestInitWithJson = RequestInit & {
  json?: unknown;
};

export async function apiRequest<T>(
  path: string,
  init?: RequestInitWithJson,
): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");

  let body = init?.body;
  if (init?.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }

  const response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
    ...init,
    headers,
    body,
  });

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function apiRequestData<T>(
  path: string,
  init?: RequestInitWithJson,
): Promise<T> {
  const envelope = await apiRequest<ApiSuccessEnvelope<T>>(path, init);
  return envelope.data;
}
