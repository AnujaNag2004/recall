"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  CircleAlert,
  ExternalLink,
  GraduationCap,
  Loader2,
  RotateCw,
  Sparkles,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ErrorState, PageBody } from "@/components/app/page-states";
import { useUpdateTask } from "@/components/tasks/task-actions";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  apiFetch,
  apiJson,
  type Resource,
  type SaveDetail,
  streamEvents,
  type Task,
} from "@/lib/api/client";
import { formatDateTime, formatTimestamp, SOURCE_LABELS } from "@/lib/format";
import { cn } from "@/lib/utils";
import { SaveChat } from "./save-chat";

function isProcessing(save: SaveDetail | undefined) {
  return save?.status === "pending" || save?.status === "processing";
}

/** Follows ingestion live, then refreshes the card with what it found. */
function useLiveProgress(save: SaveDetail | undefined, id: string) {
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<string | null>(null);
  const processing = isProcessing(save);

  useEffect(() => {
    if (!processing) return;
    const controller = new AbortController();
    void streamEvents<{ status: string; stage: string | null }>(
      `/saves/${id}/events`,
      (event) => {
        setStage(event.stage);
        if (event.status === "ready" || event.status === "failed") {
          void queryClient.invalidateQueries({ queryKey: ["save", id] });
          void queryClient.invalidateQueries({ queryKey: ["saves"] });
        }
      },
      { signal: controller.signal },
    ).catch(() => {
      // A dropped connection isn't fatal: the page polling below still catches the result.
    });
    return () => controller.abort();
  }, [processing, id, queryClient]);

  return stage;
}

function Original({ save, seekTo }: { save: SaveDetail; seekTo: number | null }) {
  if (save.embed_youtube_id) {
    const start = seekTo === null ? "" : `&start=${Math.floor(seekTo)}&autoplay=1`;
    return (
      <iframe
        // Changing the key reloads the player at the chosen moment.
        key={seekTo}
        src={`https://www.youtube-nocookie.com/embed/${save.embed_youtube_id}?rel=0${start}`}
        title={save.title ?? "Video"}
        className="aspect-video w-full rounded-xl border"
        allow="autoplay; encrypted-media; picture-in-picture"
        allowFullScreen
        sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
      />
    );
  }
  if (save.file_url && save.file_type === "image") {
    // eslint-disable-next-line @next/next/no-img-element -- a short-lived signed URL can't go through the image optimizer
    return <img src={save.file_url} alt={save.title ?? "Saved image"} className="w-full rounded-xl border" />;
  }
  if (save.file_url && save.file_type === "pdf") {
    return (
      <object data={save.file_url} type="application/pdf" className="h-[70vh] w-full rounded-xl border">
        <a href={save.file_url} className="text-sm text-primary underline">
          Open the PDF
        </a>
      </object>
    );
  }
  if (save.file_url && save.file_type === "audio") {
    return <audio controls src={save.file_url} className="w-full" />;
  }
  if (save.file_url && save.file_type === "video") {
    return <video controls src={save.file_url} className="w-full rounded-xl border" />;
  }
  return save.raw_text ? (
    <article className="max-h-[70vh] overflow-y-auto rounded-xl border p-4 text-sm leading-relaxed whitespace-pre-wrap sm:p-5">
      {save.raw_text}
    </article>
  ) : null;
}

function ResourceRow({ resource, onSeek }: { resource: Resource; onSeek: (s: number) => void }) {
  return (
    <li className="flex gap-3 py-3 first:pt-0 last:pb-0">
      <span
        aria-hidden
        className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-xs font-semibold"
      >
        {resource.url ? resource.name[0]?.toUpperCase() : "?"}
      </span>
      <div className="min-w-0 flex-1 text-sm">
        <div className="flex flex-wrap items-center gap-x-2">
          {resource.url ? (
            <a
              href={resource.url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="inline-flex items-center gap-1 font-medium hover:underline"
            >
              {resource.name}
              <ExternalLink className="size-3" aria-hidden />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          ) : (
            <span className="font-medium">{resource.name}</span>
          )}
          {resource.pricing && resource.pricing !== "unknown" && (
            <span className="text-xs text-muted-foreground capitalize">{resource.pricing}</span>
          )}
          <span className="text-xs text-muted-foreground capitalize">{resource.entity_type}</span>
        </div>
        {resource.description && (
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{resource.description}</p>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 text-xs">
          {resource.verified ? (
            <span className="flex items-center gap-1 font-medium">
              <Check className="size-3 text-primary" aria-hidden />
              Verified · {resource.domain}
            </span>
          ) : (
            <span className="flex items-center gap-1 font-medium">
              <CircleAlert className="size-3" aria-hidden />
              {resource.url ? `Unverified · ${resource.domain}` : "No official link found"}
            </span>
          )}
          {resource.confidence !== null && (
            <span className="text-muted-foreground tabular-nums">
              {Math.round(resource.confidence * 100)}% confidence
            </span>
          )}
          {resource.mention_ts !== null && (
            <button
              type="button"
              onClick={() => onSeek(resource.mention_ts as number)}
              className="rounded font-mono text-primary tabular-nums hover:underline"
              aria-label={`Jump to ${formatTimestamp(resource.mention_ts)}`}
            >
              {formatTimestamp(resource.mention_ts)}
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

function TaskRow({ task }: { task: Task }) {
  const update = useUpdateTask();
  const suggested = task.status === "suggested";
  return (
    <li
      className={cn(
        "rounded-xl border p-3 text-sm",
        task.type === "micro_action" && suggested && "border-primary/30 bg-primary/5",
      )}
    >
      {task.type === "micro_action" && suggested && (
        <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-primary">
          <Sparkles className="size-3.5" aria-hidden />
          Smallest next step
        </p>
      )}
      <p className={cn("font-medium", task.status === "done" && "line-through opacity-60")}>
        {task.title}
      </p>
      {task.description && <p className="mt-0.5 text-xs text-muted-foreground">{task.description}</p>}
      {task.scheduled_for && (
        <p className="mt-0.5 text-xs text-muted-foreground">{formatDateTime(task.scheduled_for)}</p>
      )}
      {suggested ? (
        <div className="mt-2 flex gap-2">
          <Button
            size="sm"
            disabled={update.isPending}
            onClick={() => update.mutate({ id: task.id, status: "accepted" })}
          >
            Add to tasks
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={update.isPending}
            onClick={() => update.mutate({ id: task.id, status: "let_go" })}
          >
            Dismiss
          </Button>
        </div>
      ) : (
        <p className="mt-1 text-xs text-muted-foreground capitalize">
          {task.status === "let_go" ? "Let go" : task.status}
        </p>
      )}
    </li>
  );
}

export function SmartCard() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [seekTo, setSeekTo] = useState<number | null>(null);

  const query = useQuery({
    queryKey: ["save", id],
    queryFn: () => apiFetch<SaveDetail>(`/saves/${id}`),
    refetchInterval: (state) => (isProcessing(state.state.data) ? 5000 : false),
  });
  const save = query.data;
  const liveStage = useLiveProgress(save, id);

  const retry = useMutation({
    mutationFn: () => apiJson(`/saves/${id}/retry`, "POST"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["save", id] }),
    onError: (error) => toast.error(error.message),
  });
  const remove = useMutation({
    mutationFn: () => apiFetch(`/saves/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["saves"] });
      toast("Deleted.");
      router.replace("/library");
    },
    onError: (error) => toast.error(error.message),
  });
  const flashcards = useMutation({
    mutationFn: () => apiJson<unknown[]>(`/saves/${id}/flashcards`, "POST"),
    onSuccess: (cards) => toast.success(`Made ${cards.length} flashcards. They're in Learn.`),
    onError: (error) => toast.error(error.message),
  });

  if (query.isPending) {
    return (
      <PageBody>
        <Skeleton className="h-8 w-2/3 rounded-lg" />
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </PageBody>
    );
  }
  if (query.isError || !save) {
    return (
      <PageBody>
        <ErrorState message={query.error?.message} onRetry={() => void query.refetch()} />
      </PageBody>
    );
  }

  const seek = (seconds: number) => setSeekTo(seconds);
  const processing = isProcessing(save);
  const title = save.title || save.source_url || "Untitled save";

  return (
    <PageBody className="max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            {SOURCE_LABELS[save.source_type] ?? save.source_type}
            {save.mode && <span className="capitalize"> · {save.mode}</span>}
            {save.intent && <span> · Saved to {save.intent}</span>}
            {save.author && <span> · {save.author}</span>}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight break-words">{title}</h1>
          {save.source_url && (
            <a
              href={save.source_url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              Open original
              <ExternalLink className="size-3" aria-hidden />
            </a>
          )}
          {save.topics.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {save.topics.map((topic) => (
                <Link
                  key={topic.id}
                  href={`/library?topic=${topic.id}`}
                  className="rounded-full bg-muted px-2.5 py-0.5 text-xs hover:bg-muted/70"
                >
                  {topic.name}
                </Link>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1">
          {save.status === "ready" && (
            <Button
              variant="outline"
              size="sm"
              disabled={flashcards.isPending}
              onClick={() => flashcards.mutate()}
            >
              <GraduationCap aria-hidden />
              {flashcards.isPending ? "Making…" : "Make flashcards"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="size-9 text-muted-foreground"
            aria-label="Delete this save"
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm("Delete this save and everything made from it?")) remove.mutate();
            }}
          >
            <Trash2 aria-hidden />
          </Button>
        </div>
      </div>

      {processing && (
        <div role="status" className="mt-6 flex items-center gap-3 rounded-xl border bg-card p-4 text-sm">
          <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
          <span>{liveStage ?? save.stage ?? "Waiting to start"}…</span>
        </div>
      )}
      {save.status === "failed" && (
        <div role="alert" className="mt-6 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <p className="font-medium">We couldn&apos;t process this.</p>
          <p className="mt-1 text-muted-foreground">{save.error}</p>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            disabled={retry.isPending}
            onClick={() => retry.mutate()}
          >
            <RotateCw aria-hidden />
            Try again
          </Button>
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="min-w-0 space-y-4">
          <Original save={save} seekTo={seekTo} />
          {save.transcript.length > 0 && (
            <div>
              <h2 className="text-sm font-medium">Transcript</h2>
              <ul className="mt-2 max-h-96 space-y-0.5 overflow-y-auto">
                {save.transcript.map((line, index) => (
                  <li key={index}>
                    <button
                      type="button"
                      onClick={() => seek(line.start)}
                      className="flex w-full gap-3 rounded-lg px-2 py-1 text-left text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      <span className="mt-0.5 font-mono text-xs text-primary tabular-nums">
                        {formatTimestamp(line.start)}
                      </span>
                      <span>{line.text}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="min-w-0">
          <Tabs defaultValue="summary" className="gap-4">
            <TabsList className="grid w-full grid-cols-4 group-data-horizontal/tabs:h-10">
              <TabsTrigger value="summary" className="px-1 text-xs sm:text-sm">Summary</TabsTrigger>
              <TabsTrigger value="resources" className="px-1 text-xs sm:text-sm">Resources</TabsTrigger>
              <TabsTrigger value="actions" className="px-1 text-xs sm:text-sm">Actions</TabsTrigger>
              <TabsTrigger value="chat" className="px-1 text-xs sm:text-sm">Chat</TabsTrigger>
            </TabsList>

            <TabsContent value="summary">
              {save.summary ? (
                <>
                  <p className="leading-relaxed">{save.summary}</p>
                  {save.key_points.length > 0 && (
                    <>
                      <h2 className="mt-6 text-xs font-medium text-muted-foreground">Key points</h2>
                      <ul className="mt-2 space-y-2">
                        {save.key_points.map((point) => (
                          <li key={point} className="flex gap-2 text-muted-foreground">
                            <span className="mt-2 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
                            {point}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </>
              ) : (
                <p className="text-muted-foreground">The summary will appear here.</p>
              )}
              {save.related.length > 0 && (
                <>
                  <h2 className="mt-6 text-xs font-medium text-muted-foreground">Related saves</h2>
                  <ul className="mt-2 space-y-1">
                    {save.related.map((related) => (
                      <li key={related.id}>
                        <Link href={`/saves/${related.id}`} className="text-primary hover:underline">
                          {related.title ?? "Untitled save"}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </TabsContent>

            <TabsContent value="resources">
              {save.resources.length ? (
                <ul className="divide-y">
                  {save.resources.map((resource) => (
                    <ResourceRow key={resource.id} resource={resource} onSeek={seek} />
                  ))}
                </ul>
              ) : (
                <p className="text-muted-foreground">
                  {processing ? "Looking for tools and links…" : "No tools or links were mentioned."}
                </p>
              )}
            </TabsContent>

            <TabsContent value="actions">
              {save.tasks.length ? (
                <>
                  <p className="mb-3 text-muted-foreground">
                    Nothing joins your tasks until you add it.
                  </p>
                  <ul className="space-y-2">
                    {save.tasks
                      .slice()
                      .sort((a, b) => Number(b.type === "micro_action") - Number(a.type === "micro_action"))
                      .map((task) => (
                        <TaskRow key={task.id} task={task} />
                      ))}
                  </ul>
                  <Link href="/tasks" className={cn(buttonVariants({ variant: "link" }), "mt-2 px-0")}>
                    Go to Tasks
                  </Link>
                </>
              ) : (
                <p className="text-muted-foreground">
                  {processing ? "Planning what to do…" : "Nothing here needs doing."}
                </p>
              )}
            </TabsContent>

            <TabsContent value="chat" keepMounted>
              {save.status === "ready" ? (
                <SaveChat saveId={id} onSeek={seek} />
              ) : (
                <p className="text-muted-foreground">Chat opens when this finishes processing.</p>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </PageBody>
  );
}
