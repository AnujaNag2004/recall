"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, CalendarClock, GraduationCap, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useMe, useWorkspaces } from "@/components/app/app-context";
import { ErrorState, PageBody } from "@/components/app/page-states";
import { SaveCard } from "@/components/saves/save-card";
import { useRespondToTask, useUpdateTask } from "@/components/tasks/task-actions";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, type HomeData, type Task } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ScoreRing({ ratio, label }: { ratio: number; label: string }) {
  const percent = Math.round(ratio * 100);
  return (
    <div className="relative size-28 shrink-0">
      <svg viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden>
        <circle cx="60" cy="60" r="52" fill="none" strokeWidth="8" className="stroke-muted" />
        <circle
          cx="60"
          cy="60"
          r="52"
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          pathLength="100"
          strokeDasharray={`${percent} 100`}
          className="stroke-primary transition-[stroke-dasharray] duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tracking-tight tabular-nums">{percent}%</span>
        <span className="text-[11px] text-muted-foreground tabular-nums">{label}</span>
      </div>
    </div>
  );
}

function FollowUp({ task }: { task: Task }) {
  const respond = useRespondToTask();
  const skipped = (task.skip_count ?? 0) >= 2;
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="text-xs text-muted-foreground">You planned to:</p>
      <p className="mt-0.5 font-medium">{task.title}</p>
      {task.save_id && task.save_title && (
        <Link href={`/saves/${task.save_id}`} className="text-xs text-muted-foreground hover:underline">
          From {task.save_title}
        </Link>
      )}
      <p className="mt-3 text-sm font-medium">
        {skipped ? "This keeps slipping. Keep it, or let it go?" : "Did you do it?"}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={respond.isPending}
          onClick={() => respond.mutate({ id: task.id, answer: "done" })}
        >
          Done
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={respond.isPending}
          onClick={() => respond.mutate({ id: task.id, answer: "not_yet" })}
        >
          {skipped ? "Keep it" : "Not yet"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={respond.isPending}
          onClick={() => respond.mutate({ id: task.id, answer: "let_go" })}
        >
          Let go
        </Button>
      </div>
    </li>
  );
}

function Suggestion({ task }: { task: Task }) {
  const update = useUpdateTask();
  return (
    <li className="rounded-xl border border-primary/30 bg-primary/5 p-3 text-sm">
      <p className="font-medium">{task.title}</p>
      {task.scheduled_for && (
        <p className="mt-0.5 text-xs text-muted-foreground">
          Suggested for {formatDateTime(task.scheduled_for)}
        </p>
      )}
      <div className="mt-2 flex gap-2">
        <Button
          size="sm"
          disabled={update.isPending}
          onClick={() => update.mutate({ id: task.id, status: "accepted" })}
        >
          Accept
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
    </li>
  );
}

export function HomeView() {
  const { data: me } = useMe();
  const { active } = useWorkspaces();
  const queryClient = useQueryClient();
  const firstName = me?.user.name?.split(" ")[0];

  const home = useQuery({
    queryKey: ["home", active?.id],
    queryFn: () => apiFetch<HomeData>(`/workspaces/${active?.id}/home`),
    enabled: Boolean(active),
  });

  const dismiss = useMutation({
    mutationFn: (id: string) => apiFetch(`/recall-cards/${id}/dismiss`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["home"] }),
  });

  const data = home.data;
  const isEmpty = data && data.recent_saves.length === 0;

  return (
    <PageBody>
      <h1 className="text-2xl font-semibold tracking-tight">
        {firstName ? `Welcome, ${firstName}` : "Welcome"}
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">
        {active ? `You're in ${active.name}.` : "Here's where your day starts."}
      </p>

      {home.isPending && (
        <div className="mt-6 grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      )}
      {home.isError && (
        <div className="mt-6">
          <ErrorState message={home.error.message} onRetry={() => void home.refetch()} />
        </div>
      )}
      {isEmpty && (
        <div className="mt-8 rounded-2xl border border-dashed px-6 py-14 text-center">
          <Sparkles className="mx-auto size-6 text-primary" aria-hidden />
          <h2 className="mt-4 text-lg font-semibold tracking-tight">Nothing saved yet</h2>
          <p className="mx-auto mt-1.5 max-w-sm text-sm text-pretty text-muted-foreground">
            Your next steps, and the saves that matter right now, will show up here once you start
            saving.
          </p>
          <Link href="/inbox" className={cn(buttonVariants(), "mt-6 h-10 rounded-lg px-4")}>
            Save your first link
          </Link>
        </div>
      )}

      {data && !isEmpty && (
        <div className="mt-6 grid grid-cols-1 gap-8 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-8">
            {data.recall_cards.length > 0 && (
              <section aria-labelledby="right-now">
                <h2 id="right-now" className="flex items-center gap-2 text-sm font-medium">
                  <BellRing className="size-4 text-primary" aria-hidden />
                  Right now for you
                </h2>
                <ul className="mt-3 space-y-2">
                  {data.recall_cards.map((card) => (
                    <li key={card.id} className="relative rounded-xl border bg-card p-4 pr-10 shadow-sm">
                      <p className="font-medium">{card.title}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{card.body}</p>
                      <div className="mt-2 flex flex-wrap gap-x-3 text-xs">
                        {card.save_ids.map((id, index) => (
                          <Link key={id} href={`/saves/${id}`} className="text-primary hover:underline">
                            Save {index + 1}
                          </Link>
                        ))}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="absolute top-2 right-2 text-muted-foreground"
                        aria-label={`Dismiss ${card.title}`}
                        onClick={() => dismiss.mutate(card.id)}
                      >
                        <X aria-hidden />
                      </Button>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {data.followups.length > 0 && (
              <section aria-label="Follow-ups">
                <ul className="space-y-2">
                  {data.followups.map((task) => (
                    <FollowUp key={task.id} task={task} />
                  ))}
                </ul>
              </section>
            )}

            <section aria-labelledby="today">
              <h2 id="today" className="flex items-center gap-2 text-sm font-medium">
                <CalendarClock className="size-4 text-muted-foreground" aria-hidden />
                Today
              </h2>
              {data.today.length ? (
                <ul className="mt-3 divide-y rounded-xl border">
                  {data.today.map((task) => (
                    <li key={task.id} className="flex items-center justify-between gap-3 p-3 text-sm">
                      <span className="min-w-0 truncate">{task.title}</span>
                      {task.scheduled_for && (
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {formatDateTime(task.scheduled_for)}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">Nothing scheduled for today.</p>
              )}
            </section>

            {data.suggested.length > 0 && (
              <section aria-labelledby="suggested">
                <h2 id="suggested" className="text-sm font-medium">
                  Suggested first steps
                </h2>
                <ul className="mt-3 space-y-2">
                  {data.suggested.map((task) => (
                    <Suggestion key={task.id} task={task} />
                  ))}
                </ul>
              </section>
            )}

            <section aria-labelledby="recent">
              <h2 id="recent" className="text-sm font-medium">
                Recent saves
              </h2>
              <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                {data.recent_saves.map((save) => (
                  <li key={save.id}>
                    <SaveCard save={save} />
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <aside className="space-y-4">
            <Link
              href="/insights"
              className="block rounded-xl border bg-card p-4 shadow-sm transition-colors hover:bg-muted/50"
            >
              <h2 className="text-sm font-medium">Save-to-Action score</h2>
              <div className="mt-3 flex items-center gap-4">
                <ScoreRing
                  ratio={data.score.ratio}
                  label={`${data.score.acted} of ${data.score.total}`}
                />
                <p className="text-sm text-muted-foreground">
                  {data.streak_days > 0
                    ? `${data.streak_days} day streak`
                    : "Finish one small step to start a streak."}
                </p>
              </div>
            </Link>
            <Link
              href="/learn"
              className="flex items-center gap-3 rounded-xl border bg-card p-4 shadow-sm transition-colors hover:bg-muted/50"
            >
              <GraduationCap className="size-5 text-primary" aria-hidden />
              <div>
                <p className="text-sm font-medium">
                  {data.review_count ? `${data.review_count} cards to review` : "No cards due"}
                </p>
                <p className="text-xs text-muted-foreground">Learn Mode</p>
              </div>
            </Link>
          </aside>
        </div>
      )}
    </PageBody>
  );
}
