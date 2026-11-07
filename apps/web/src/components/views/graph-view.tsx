"use client";

import "@xyflow/react/dist/style.css";

import { useQuery } from "@tanstack/react-query";
import { Background, Controls, type Edge, type Node, ReactFlow } from "@xyflow/react";
import { Network } from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { useWorkspaces } from "@/components/app/app-context";
import { EmptyState, ErrorState, PageBody, PageHeader } from "@/components/app/page-states";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, type GraphData } from "@/lib/api/client";

/** Rings by importance: the most-saved topics sit in the middle. */
function layout(data: GraphData): { nodes: Node[]; edges: Edge[] } {
  const sorted = [...data.nodes].sort((a, b) => b.save_count - a.save_count);
  const nodes: Node[] = [];
  let index = 0;
  let ring = 0;
  while (index < sorted.length) {
    const capacity = ring === 0 ? 1 : ring * 7;
    const radius = ring * 170;
    const members = sorted.slice(index, index + capacity);
    members.forEach((topic, position) => {
      const angle = (position / members.length) * 2 * Math.PI;
      const flag = topic.obsession ? "obsession" : topic.blind_spot ? "blind spot" : null;
      nodes.push({
        id: topic.id,
        position: { x: radius * Math.cos(angle), y: radius * Math.sin(angle) },
        data: {
          label: `${topic.name} (${topic.save_count})${flag ? ` · ${flag}` : ""}`,
        },
        ariaLabel: `${topic.name}: ${topic.save_count} saves, ${topic.done_count} acted on${flag ? `, ${flag}` : ""}. Open in Library.`,
        style: {
          background: topic.obsession ? "var(--primary)" : "var(--card)",
          color: topic.obsession ? "var(--primary-foreground)" : "var(--card-foreground)",
          border: topic.blind_spot ? "2px dashed var(--primary)" : "1px solid var(--border)",
          borderRadius: 12,
          fontSize: 12 + Math.min(topic.save_count, 6),
          width: "auto",
          cursor: "pointer",
        },
      });
    });
    index += capacity;
    ring += 1;
  }
  return {
    nodes,
    edges: data.edges.map((edge) => ({
      id: `${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      style: { stroke: "var(--muted-foreground)", strokeOpacity: 0.5 },
    })),
  };
}

export function GraphView() {
  const router = useRouter();
  const { active } = useWorkspaces();
  const { resolvedTheme } = useTheme();
  const graph = useQuery({
    queryKey: ["graph", active?.id],
    queryFn: () => apiFetch<GraphData>(`/workspaces/${active?.id}/graph`),
    enabled: Boolean(active),
  });
  const flow = useMemo(() => (graph.data ? layout(graph.data) : null), [graph.data]);

  if (graph.isPending || graph.isError || !flow || flow.nodes.length === 0) {
    return (
      <PageBody>
        <PageHeader title="Knowledge Graph" />
        <div className="mt-6">
          {graph.isPending ? (
            <Skeleton className="h-96 rounded-xl" />
          ) : graph.isError ? (
            <ErrorState message={graph.error.message} onRetry={() => void graph.refetch()} />
          ) : (
            <EmptyState
              icon={Network}
              title="No topics yet"
              body="Topics appear as your saves finish processing, connecting what you've saved."
            />
          )}
        </div>
      </PageBody>
    );
  }

  return (
    <div className="relative h-full min-h-96">
      <div className="absolute top-4 left-4 z-10 rounded-xl border bg-card/90 p-3 text-xs shadow-sm backdrop-blur">
        <h1 className="text-sm font-semibold tracking-tight">Knowledge Graph</h1>
        <p className="mt-1 text-muted-foreground">Select a topic to see its saves.</p>
        <p className="mt-2 flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-primary" aria-hidden />
          Obsession: saved far more than usual
        </p>
        <p className="mt-1 flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm border-2 border-dashed border-primary" aria-hidden />
          Blind spot: saved, never acted on
        </p>
      </div>
      <ReactFlow
        nodes={flow.nodes}
        edges={flow.edges}
        fitView
        colorMode={resolvedTheme === "dark" ? "dark" : "light"}
        nodesConnectable={false}
        onNodeClick={(_, node) => router.push(`/library?topic=${node.id}`)}
      >
        <Background gap={24} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
