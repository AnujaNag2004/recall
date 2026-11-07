"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import Link from "next/link";
import { useWorkspaces } from "@/components/app/app-context";
import { EmptyState, ErrorState, PageBody, PageHeader } from "@/components/app/page-states";
import { Skeleton } from "@/components/ui/skeleton";
import { type AgentRun, apiFetch } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";

export function AgentRunsView() {
  const { active } = useWorkspaces();
  const runs = useQuery({
    queryKey: ["agent-runs", active?.id],
    queryFn: () => apiFetch<AgentRun[]>(`/workspaces/${active?.id}/agent-runs`),
    enabled: Boolean(active),
    retry: false,
  });
  return (
    <PageBody>
      <PageHeader title="Agent runs" lead="Recent ingestion runs in this workspace. Admins only." />
      <div className="mt-6">
        {runs.isPending ? (
          <Skeleton className="h-48 rounded-xl" />
        ) : runs.isError ? (
          <ErrorState message={runs.error.message} onRetry={() => void runs.refetch()} />
        ) : runs.data.length === 0 ? (
          <EmptyState icon={Activity} title="No runs yet" body="Each save you process appears here." />
        ) : (
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead className="border-b text-xs text-muted-foreground">
                <tr>
                  <th className="p-3 font-medium">When</th>
                  <th className="p-3 font-medium">Status</th>
                  <th className="p-3 font-medium">Latency</th>
                  <th className="p-3 font-medium">Save</th>
                  <th className="p-3 font-medium">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {runs.data.map((run) => (
                  <tr key={run.id}>
                    <td className="p-3 whitespace-nowrap">{formatDateTime(run.created_at)}</td>
                    <td className="p-3 capitalize">{run.status}</td>
                    <td className="p-3 tabular-nums">
                      {run.latency_ms === null ? "–" : `${(run.latency_ms / 1000).toFixed(1)}s`}
                    </td>
                    <td className="p-3">
                      {run.save_id && (
                        <Link href={`/saves/${run.save_id}`} className="text-primary hover:underline">
                          Open
                        </Link>
                      )}
                    </td>
                    <td className="max-w-64 truncate p-3 text-xs text-muted-foreground" title={run.error ?? undefined}>
                      {run.error ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageBody>
  );
}
