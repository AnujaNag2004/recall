"use client";

import { useQuery } from "@tanstack/react-query";
import { Inbox } from "lucide-react";
import { useWorkspaces } from "@/components/app/app-context";
import { EmptyState, ErrorState, PageBody, PageHeader } from "@/components/app/page-states";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, type SaveList } from "@/lib/api/client";
import { CaptureForm } from "./capture-form";
import { SaveCard } from "./save-card";

export function InboxView() {
  const { active } = useWorkspaces();
  const saves = useQuery({
    queryKey: ["saves", active?.id, "recent"],
    queryFn: () => apiFetch<SaveList>(`/workspaces/${active?.id}/saves?limit=12`),
    enabled: Boolean(active),
    // Keeps cards moving while they process, then stops asking.
    refetchInterval: (query) =>
      query.state.data?.items.some((s) => s.status === "pending" || s.status === "processing")
        ? 3000
        : false,
  });

  return (
    <PageBody>
      <PageHeader title="Inbox" lead="Save anything. Recall will work out what to do with it." />
      <div className="mt-6">
        <CaptureForm />
      </div>
      <h2 className="mt-10 text-sm font-medium">Recently saved</h2>
      <div className="mt-3">
        {saves.isPending ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
        ) : saves.isError ? (
          <ErrorState message={saves.error.message} onRetry={() => void saves.refetch()} />
        ) : saves.data.items.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="Nothing saved yet"
            body="Paste your first link above, and you'll watch it turn into a Smart Card."
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {saves.data.items.map((save) => (
              <li key={save.id}>
                <SaveCard save={save} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </PageBody>
  );
}
