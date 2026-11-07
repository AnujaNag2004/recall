import { createClient } from "@/lib/supabase/client";
import type { components } from "./schema";

export type Me = components["schemas"]["MeOut"];
export type Workspace = components["schemas"]["WorkspaceOut"];

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** Calls the Recall API as the signed-in user. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const { data } = await createClient().auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new ApiError(401, "Not signed in");

  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: { ...init?.headers, Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new ApiError(response.status, `Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}
