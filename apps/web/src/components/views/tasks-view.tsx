"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, CheckSquare, Download, Trash2 } from "lucide-react";
import Link from "next/link";
import type { FormEvent } from "react";
import { toast } from "sonner";
import { useWorkspaces } from "@/components/app/app-context";
import { EmptyState, ErrorState, PageBody, PageHeader } from "@/components/app/page-states";
import { useRespondToTask, useUpdateTask } from "@/components/tasks/task-actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiDownload, apiFetch, apiJson, type CalendarEvent, type Task } from "@/lib/api/client";
import { formatDateTime, toLocalInput } from "@/lib/format";

const endOfToday = () => {
  const date = new Date();
  date.setHours(23, 59, 59, 999);
  return date;
};

function TaskCard({ task, googleConnected }: { task: Task; googleConnected: boolean }) {
  const respond = useRespondToTask();
  const update = useUpdateTask();
  const addToGoogle = useMutation({
    mutationFn: () => apiJson(`/tasks/${task.id}/add-to-google`, "POST"),
    onSuccess: () => toast.success("Added to Google Calendar."),
    onError: (error) => toast.error(error.message),
  });
  const done = task.status === "done";
  return (
    <li className="rounded-xl border bg-card p-3 text-sm shadow-sm">
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={done}
          disabled={done || respond.isPending}
          aria-label={`Mark "${task.title}" as done`}
          onChange={() => respond.mutate({ id: task.id, answer: "done" })}
          className="mt-0.5 size-4 accent-[var(--primary)]"
        />
        <div className="min-w-0 flex-1">
          <p className={done ? "font-medium line-through opacity-60" : "font-medium"}>{task.title}</p>
          {task.save_id && task.save_title && (
            <Link href={`/saves/${task.save_id}`} className="block truncate text-xs text-muted-foreground hover:underline">
              {task.save_title}
            </Link>
          )}
          {(task.scheduled_for || task.due_at) && (
            <p className="text-xs text-muted-foreground">
              {formatDateTime((task.scheduled_for ?? task.due_at) as string)}
            </p>
          )}
        </div>
      </div>
      {!done && (
        <div className="mt-2 flex flex-wrap items-center gap-1 pl-7">
          <label className="sr-only" htmlFor={`when-${task.id}`}>
            Reschedule {task.title}
          </label>
          <input
            id={`when-${task.id}`}
            type="datetime-local"
            defaultValue={task.scheduled_for ? toLocalInput(new Date(task.scheduled_for)) : ""}
            onBlur={(event) => {
              if (!event.target.value) return;
              const next = new Date(event.target.value).toISOString();
              if (next !== task.scheduled_for) update.mutate({ id: task.id, scheduled_for: next });
            }}
            className="h-7 rounded-md border bg-background px-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {googleConnected && (task.scheduled_for || task.due_at) && (
            <Button
              size="xs"
              variant="ghost"
              disabled={addToGoogle.isPending}
              onClick={() => addToGoogle.mutate()}
            >
              <CalendarPlus aria-hidden />
              Add to Google
            </Button>
          )}
          <Button
            size="xs"
            variant="ghost"
            disabled={respond.isPending}
            onClick={() => respond.mutate({ id: task.id, answer: "let_go" })}
          >
            Let go
          </Button>
        </div>
      )}
    </li>
  );
}

function Column({ title, tasks, google, empty }: { title: string; tasks: Task[]; google: boolean; empty: string }) {
  return (
    <section aria-label={title} className="min-w-0">
      <h2 className="text-sm font-medium">
        {title} <span className="text-muted-foreground tabular-nums">{tasks.length}</span>
      </h2>
      {tasks.length ? (
        <ul className="mt-3 space-y-2">
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} googleConnected={google} />
          ))}
        </ul>
      ) : (
        <p className="mt-3 rounded-xl border border-dashed p-4 text-center text-xs text-muted-foreground">
          {empty}
        </p>
      )}
    </section>
  );
}

function CalendarPanel({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();
  const events = useQuery({
    queryKey: ["calendar", workspaceId],
    queryFn: () => apiFetch<CalendarEvent[]>(`/workspaces/${workspaceId}/calendar/events`),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["calendar", workspaceId] });
  const add = useMutation({
    mutationFn: (body: object) => apiJson(`/workspaces/${workspaceId}/calendar/events`, "POST", body),
    onSuccess: async () => {
      await refresh();
      toast.success("Added. Recall will bring back related saves beforehand.");
    },
    onError: (error) => toast.error(error.message),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiFetch(`/calendar/events/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
    onError: (error) => toast.error(error.message),
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    add.mutate({
      title: String(data.get("title")),
      starts_at: new Date(String(data.get("starts_at"))).toISOString(),
      is_deadline: data.get("is_deadline") === "on",
    });
    form.reset();
  };

  const upcoming = (events.data ?? []).filter((e) => new Date(e.starts_at) >= new Date());

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <form onSubmit={submit} className="space-y-3 self-start rounded-xl border bg-card p-4 shadow-sm">
        <h2 className="text-sm font-medium">Add an event or deadline</h2>
        <p className="text-xs text-muted-foreground">
          Exams and meetings here trigger just-in-time recall.
        </p>
        <Input name="title" required maxLength={200} placeholder="Algorithms exam" aria-label="Title" className="h-9" />
        <Input name="starts_at" required type="datetime-local" aria-label="When" className="h-9" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="is_deadline" className="size-4 accent-[var(--primary)]" />
          This is a deadline
        </label>
        <Button type="submit" disabled={add.isPending}>
          Add
        </Button>
      </form>
      <div className="min-w-0">
        <h2 className="text-sm font-medium">Coming up</h2>
        {events.isPending ? (
          <Skeleton className="mt-3 h-24 rounded-xl" />
        ) : upcoming.length ? (
          <ul className="mt-3 divide-y rounded-xl border">
            {upcoming.map((event) => (
              <li key={event.id} className="flex items-center justify-between gap-3 p-3 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium">{event.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDateTime(event.starts_at)}
                    {event.is_deadline && " · Deadline"}
                    {event.source === "google" && " · Google Calendar"}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="text-muted-foreground"
                  aria-label={`Delete ${event.title}`}
                  onClick={() => remove.mutate(event.id)}
                >
                  <Trash2 aria-hidden />
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
            Nothing coming up.
          </p>
        )}
      </div>
    </div>
  );
}

export function TasksView() {
  const { active } = useWorkspaces();
  const queryClient = useQueryClient();
  const tasks = useQuery({
    queryKey: ["tasks", active?.id],
    queryFn: () =>
      apiFetch<Task[]>(`/workspaces/${active?.id}/tasks?status=accepted&status=done&limit=200`),
    enabled: Boolean(active),
  });
  const google = useQuery({
    queryKey: ["google-status"],
    queryFn: () => apiFetch<{ configured: boolean; connected: boolean }>("/integrations/google/status"),
  });
  const create = useMutation({
    mutationFn: (title: string) => apiJson(`/workspaces/${active?.id}/tasks`, "POST", { title }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
    onError: (error) => toast.error(error.message),
  });

  const all = tasks.data ?? [];
  const open = all.filter((t) => t.status === "accepted");
  // Only ever called for loaded tasks, so the clock isn't read during prerendering.
  const isToday = (t: Task) => {
    const when = t.scheduled_for ?? t.due_at;
    return !when || new Date(when) <= endOfToday();
  };

  const add = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const title = String(new FormData(form).get("title")).trim();
    if (title) create.mutate(title);
    form.reset();
  };

  return (
    <PageBody>
      <PageHeader
        title="Tasks"
        lead="Small steps from your saves, and anything else you add."
        actions={
          active && (
            <Button
              variant="outline"
              onClick={() =>
                void apiDownload(`/workspaces/${active.id}/calendar/export.ics`, "recall.ics").catch(
                  (error: Error) => toast.error(error.message),
                )
              }
            >
              <Download aria-hidden />
              Export .ics
            </Button>
          )
        }
      />
      <Tabs defaultValue="board" className="mt-6 gap-5">
        <TabsList className="group-data-horizontal/tabs:h-10">
          <TabsTrigger value="board" className="px-4">Board</TabsTrigger>
          <TabsTrigger value="calendar" className="px-4">Calendar</TabsTrigger>
        </TabsList>
        <TabsContent value="board">
          <form onSubmit={add} className="flex gap-2">
            <Input name="title" required maxLength={300} placeholder="Add a task" aria-label="Add a task" className="h-10" />
            <Button type="submit" className="h-10" disabled={create.isPending || !active}>
              Add
            </Button>
          </form>
          <div className="mt-6">
            {tasks.isPending ? (
              <div className="grid gap-4 md:grid-cols-3">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-40 rounded-xl" />
                ))}
              </div>
            ) : tasks.isError ? (
              <ErrorState message={tasks.error.message} onRetry={() => void tasks.refetch()} />
            ) : all.length === 0 ? (
              <EmptyState
                icon={CheckSquare}
                title="No tasks yet"
                body="Add one above, or accept a suggested step on any Smart Card."
              />
            ) : (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                <Column title="Today" tasks={open.filter(isToday)} google={Boolean(google.data?.connected)} empty="Nothing for today." />
                <Column title="Upcoming" tasks={open.filter((t) => !isToday(t))} google={Boolean(google.data?.connected)} empty="Nothing coming up." />
                <Column title="Done" tasks={all.filter((t) => t.status === "done")} google={false} empty="Done tasks land here." />
              </div>
            )}
          </div>
        </TabsContent>
        <TabsContent value="calendar">{active && <CalendarPanel workspaceId={active.id} />}</TabsContent>
      </Tabs>
    </PageBody>
  );
}
