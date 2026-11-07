"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { BookOpen, Search, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useWorkspaces } from "@/components/app/app-context";
import { EmptyState, ErrorState, PageBody, PageHeader } from "@/components/app/page-states";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, type GraphData, type SaveList } from "@/lib/api/client";
import { SOURCE_LABELS } from "@/lib/format";
import { SaveCard } from "./save-card";

const selectClass =
  "h-9 rounded-lg border bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function LibraryView() {
  const router = useRouter();
  const params = useSearchParams();
  const { active } = useWorkspaces();
  const [search, setSearch] = useState(params.get("q") ?? "");

  const filters = {
    q: params.get("q") ?? "",
    mode: params.get("mode") ?? "",
    source_type: params.get("source_type") ?? "",
    status: params.get("status") ?? "",
    topic: params.get("topic") ?? "",
  };

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`/library?${next.toString()}`);
  };

  // Typing shouldn't send a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== filters.q) setFilter("q", search.trim());
    }, 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the typed text should re-arm this
  }, [search]);

  const topics = useQuery({
    queryKey: ["graph", active?.id],
    queryFn: () => apiFetch<GraphData>(`/workspaces/${active?.id}/graph`),
    enabled: Boolean(active),
  });

  const saves = useInfiniteQuery({
    queryKey: ["saves", active?.id, "library", filters],
    enabled: Boolean(active),
    initialPageParam: null as string | null,
    getNextPageParam: (last: SaveList) => last.next_cursor,
    queryFn: ({ pageParam }) => {
      const query = new URLSearchParams({ limit: "30" });
      for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
      if (pageParam) query.set("cursor", pageParam);
      return apiFetch<SaveList>(`/workspaces/${active?.id}/saves?${query}`);
    },
  });

  const items = saves.data?.pages.flatMap((page) => page.items) ?? [];
  const filtered = Object.values(filters).some(Boolean);

  return (
    <PageBody>
      <PageHeader title="Library" lead="Everything you've saved in this workspace." />
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search
            className="absolute top-2.5 left-2.5 size-4 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search titles, summaries and content"
            aria-label="Search your library"
            className="h-9 pl-8"
          />
        </div>
        <select
          aria-label="Filter by mode"
          className={selectClass}
          value={filters.mode}
          onChange={(event) => setFilter("mode", event.target.value)}
        >
          <option value="">All modes</option>
          <option value="life">Life</option>
          <option value="study">Study</option>
          <option value="work">Work</option>
        </select>
        <select
          aria-label="Filter by type"
          className={selectClass}
          value={filters.source_type}
          onChange={(event) => setFilter("source_type", event.target.value)}
        >
          <option value="">All types</option>
          {Object.entries(SOURCE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by status"
          className={selectClass}
          value={filters.status}
          onChange={(event) => setFilter("status", event.target.value)}
        >
          <option value="">Any status</option>
          <option value="ready">Ready</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
        </select>
        {(topics.data?.nodes.length ?? 0) > 0 && (
          <select
            aria-label="Filter by topic"
            className={selectClass}
            value={filters.topic}
            onChange={(event) => setFilter("topic", event.target.value)}
          >
            <option value="">All topics</option>
            {topics.data?.nodes.map((node) => (
              <option key={node.id} value={node.id}>
                {node.name}
              </option>
            ))}
          </select>
        )}
        {filtered && (
          <Button
            variant="ghost"
            className="h-9"
            onClick={() => {
              setSearch("");
              router.replace("/library");
            }}
          >
            <X aria-hidden />
            Clear
          </Button>
        )}
      </div>

      <div className="mt-6">
        {saves.isPending ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-32 rounded-xl" />
            ))}
          </div>
        ) : saves.isError ? (
          <ErrorState message={saves.error.message} onRetry={() => void saves.refetch()} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title={filtered ? "Nothing matches that" : "Your library is empty"}
            body={
              filtered
                ? "Try a different search, or clear the filters."
                : "Everything you save will appear here, ready to search."
            }
            action={
              !filtered && (
                <Link href="/inbox" className={buttonVariants()}>
                  Save something
                </Link>
              )
            }
          />
        ) : (
          <>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((save) => (
                <li key={save.id}>
                  <SaveCard save={save} />
                </li>
              ))}
            </ul>
            {saves.hasNextPage && (
              <div className="mt-6 text-center">
                <Button
                  variant="outline"
                  disabled={saves.isFetchingNextPage}
                  onClick={() => void saves.fetchNextPage()}
                >
                  {saves.isFetchingNextPage ? "Loading…" : "Show more"}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </PageBody>
  );
}
