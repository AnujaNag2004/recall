"use client";

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { ApiError, apiFetch, type Me, type Workspace } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

const ACTIVE_WORKSPACE_KEY = "recall.activeWorkspace";

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // Storage can be blocked, for example in a private window.
  }
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Me>("/me"),
    staleTime: 5 * 60 * 1000,
    // A sleeping server is worth retrying; a rejected token isn't.
    retry: (failures, error) =>
      !(error instanceof ApiError && error.status === 401) && failures < 2,
    retryDelay: (attempt) => 2000 * 2 ** attempt,
  });
}

/** A full page load drops every cached query, so nothing of this user's survives. */
export async function signOut() {
  await createClient().auth.signOut();
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- the reload is the point
  window.location.assign("/");
}

type WorkspaceContextValue = {
  workspaces: Workspace[];
  active: Workspace | null;
  setActive: (id: string) => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspaces() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspaces must be used inside AppProviders");
  return value;
}

function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  const [chosenId, setChosenId] = useState<string | null>(() =>
    typeof window === "undefined" ? null : readStorage(ACTIVE_WORKSPACE_KEY),
  );

  const setActive = useCallback((id: string) => {
    setChosenId(id);
    try {
      window.localStorage.setItem(ACTIVE_WORKSPACE_KEY, id);
    } catch {
      // Not remembered across visits, which is fine.
    }
  }, []);

  const value = useMemo(() => {
    const workspaces = me?.workspaces ?? [];
    // A remembered workspace may be gone, or belong to whoever used this browser last.
    const active = workspaces.find((w) => w.id === chosenId) ?? workspaces[0] ?? null;
    return { workspaces, active, setActive };
  }, [me, chosenId, setActive]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <WorkspaceProvider>{children}</WorkspaceProvider>
    </QueryClientProvider>
  );
}
