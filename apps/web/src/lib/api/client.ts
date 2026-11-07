import { createClient } from "@/lib/supabase/client";
import type { components } from "./schema";

type Schemas = components["schemas"];
export type Me = Schemas["MeOut"];
export type Workspace = Schemas["WorkspaceOut"];
export type SaveSummary = Schemas["SaveSummaryOut"];
export type SaveDetail = Schemas["SaveDetailOut"];
export type SaveList = Schemas["SaveList"];
export type Resource = Schemas["ResourceOut"];
export type Task = Schemas["TaskOut"];
export type HomeData = Schemas["HomeOut"];
export type Metrics = Schemas["MetricsOut"];
export type Flashcard = Schemas["FlashcardOut"];
export type Quiz = Schemas["Quiz"];
export type GraphData = Schemas["GraphOut"];
export type Insight = Schemas["InsightOut"];
export type CalendarEvent = Schemas["EventOut"];
export type Member = Schemas["MemberOut"];
export type Invite = Schemas["InviteOut"];
export type ApiKey = Schemas["ApiKeyOut"];
export type ApiKeyCreated = Schemas["ApiKeyCreated"];
export type Usage = Schemas["UsageOut"];
export type AgentRun = Schemas["AgentRunOut"];
export type Conversation = Schemas["ConversationOut"];
export type Message = Schemas["MessageOut"];

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await createClient().auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new ApiError(401, "Not signed in");
  return { Authorization: `Bearer ${token}` };
}

async function toError(response: Response): Promise<ApiError> {
  let message = "Something went wrong. Please try again.";
  try {
    const body = await response.json();
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      message = String(body.detail[0].msg).replace(/^Value error, /, "");
    }
  } catch {
    // Keep the generic message: this response wasn't JSON.
  }
  return new ApiError(response.status, message);
}

/** Calls the Recall API as the signed-in user. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: { ...init?.headers, ...(await authHeader()) },
  });
  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function apiJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/** Downloads through an authenticated request, then hands the browser the file. */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1${path}`, { headers: await authHeader() });
  if (!response.ok) throw await toError(response);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Reads Server-Sent Events over fetch. EventSource can't send an Authorization header,
 * and putting a token in a URL would leak it into logs.
 */
export async function streamEvents<T>(
  path: string,
  onEvent: (event: T) => void,
  init?: RequestInit & { signal?: AbortSignal },
): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: { ...init?.headers, ...(await authHeader()) },
  });
  if (!response.ok || !response.body) throw await toError(response);
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))
        .join("");
      if (data) onEvent(JSON.parse(data) as T);
    }
  }
}
