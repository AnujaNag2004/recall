"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { useMe, useWorkspaces } from "@/components/app/app-context";
import { ErrorState, PageBody, PageHeader } from "@/components/app/page-states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, apiJson, type Invite, type Member } from "@/lib/api/client";
import { formatDate } from "@/lib/format";

const ROLES = ["admin", "member", "viewer"];
const selectClass =
  "h-9 rounded-lg border bg-background px-2 text-sm capitalize outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function WorkspaceSettings() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const { active } = useWorkspaces();
  const canAdminister = active?.role === "owner" || active?.role === "admin";
  const [prepAbout, setPrepAbout] = useState("");

  const refresh = () =>
    Promise.all(
      ["members", "invites", "me"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
    );
  const onError = (error: Error) => toast.error(error.message);

  const members = useQuery({
    queryKey: ["members", active?.id],
    queryFn: () => apiFetch<Member[]>(`/workspaces/${active?.id}/members`),
    enabled: Boolean(active),
  });
  const invites = useQuery({
    queryKey: ["invites", active?.id],
    queryFn: () => apiFetch<Invite[]>(`/workspaces/${active?.id}/invites`),
    enabled: Boolean(active) && canAdminister,
  });
  const createTeam = useMutation({
    mutationFn: (name: string) => apiJson("/workspaces", "POST", { name }),
    onSuccess: async () => {
      await refresh();
      toast.success("Team created. Find it in the workspace switcher.");
    },
    onError,
  });
  const invite = useMutation({
    mutationFn: (body: object) => apiJson(`/workspaces/${active?.id}/invites`, "POST", body),
    onSuccess: refresh,
    onError,
  });
  const revoke = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/workspaces/${active?.id}/invites/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
    onError,
  });
  const changeRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      apiJson(`/workspaces/${active?.id}/members/${userId}`, "PATCH", { role }),
    onSuccess: refresh,
    onError,
  });
  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      apiFetch(`/workspaces/${active?.id}/members/${userId}`, { method: "DELETE" }),
    onSuccess: async (_, userId) => {
      await refresh();
      if (userId === me?.user.id) router.replace("/home");
    },
    onError,
  });
  const prep = useMutation({
    mutationFn: () =>
      apiJson<{ summary: string; saves: { id: string; title: string | null }[] }>(
        `/workspaces/${active?.id}/prep`,
        "POST",
        { about: prepAbout },
      ),
    onError,
  });

  const copyLink = (token: string) =>
    void navigator.clipboard
      .writeText(`${window.location.origin}/invites/${token}`)
      .then(() => toast.success("Invite link copied. Send it to them yourself."));

  return (
    <PageBody className="max-w-3xl">
      <PageHeader title="Workspace" lead={active?.name} />
      <div className="mt-6 space-y-4">
        <section className="rounded-xl border bg-card p-5 shadow-sm">
          <h2 className="font-medium tracking-tight">Members</h2>
          {members.isPending ? (
            <Skeleton className="mt-4 h-20 rounded-lg" />
          ) : members.isError ? (
            <div className="mt-4">
              <ErrorState message={members.error.message} onRetry={() => void members.refetch()} />
            </div>
          ) : (
            <ul className="mt-4 divide-y rounded-lg border">
              {members.data.map((member) => {
                const isOwner = member.role === "owner";
                const isMe = member.user_id === me?.user.id;
                return (
                  <li key={member.user_id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                    <span className="min-w-0 truncate font-medium">
                      {member.name ?? "Unnamed"}
                      {isMe && <span className="font-normal text-muted-foreground"> (you)</span>}
                    </span>
                    <div className="flex items-center gap-1">
                      {canAdminister && !isOwner ? (
                        <select
                          aria-label={`Role for ${member.name ?? "this member"}`}
                          className={selectClass}
                          value={member.role}
                          onChange={(event) =>
                            changeRole.mutate({ userId: member.user_id, role: event.target.value })
                          }
                        >
                          {ROLES.map((role) => (
                            <option key={role} value={role}>
                              {role}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span className="text-xs text-muted-foreground capitalize">{member.role}</span>
                      )}
                      {!isOwner && (canAdminister || isMe) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground"
                          onClick={() => removeMember.mutate(member.user_id)}
                        >
                          {isMe ? "Leave" : "Remove"}
                        </Button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {canAdminister && active?.type === "team" && (
          <section className="rounded-xl border bg-card p-5 shadow-sm">
            <h2 className="font-medium tracking-tight">Invite someone</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              You&apos;ll get a link to send them. It works for that email address, for 7 days.
            </p>
            <form
              className="mt-4 flex flex-wrap gap-2"
              onSubmit={(event: FormEvent<HTMLFormElement>) => {
                event.preventDefault();
                const form = event.currentTarget;
                const data = new FormData(form);
                invite.mutate({ email: data.get("email"), role: data.get("role") });
                form.reset();
              }}
            >
              <Input name="email" type="email" required placeholder="teammate@example.com" aria-label="Email" className="h-9 min-w-48 flex-1" />
              <select name="role" aria-label="Role" defaultValue="member" className={selectClass}>
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
              <Button type="submit" className="h-9" disabled={invite.isPending}>
                Create invite
              </Button>
            </form>
            {(invites.data?.length ?? 0) > 0 && (
              <ul className="mt-4 divide-y rounded-lg border">
                {invites.data?.map((item) => (
                  <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{item.email}</p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {item.role} · Expires {formatDate(item.expires_at)}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      <Button size="sm" variant="outline" onClick={() => copyLink(item.token)}>
                        <Copy aria-hidden />
                        Copy link
                      </Button>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        className="text-muted-foreground"
                        aria-label={`Revoke invite for ${item.email}`}
                        onClick={() => revoke.mutate(item.id)}
                      >
                        <Trash2 aria-hidden />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        <section className="rounded-xl border bg-card p-5 shadow-sm">
          <h2 className="font-medium tracking-tight">Prep me for a meeting</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Gathers everything saved here about a person, client or topic.
          </p>
          <form
            className="mt-4 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (prepAbout.trim()) prep.mutate();
            }}
          >
            <Input
              value={prepAbout}
              onChange={(event) => setPrepAbout(event.target.value)}
              maxLength={300}
              placeholder="Pricing call with the client"
              aria-label="What's the meeting about?"
              className="h-9"
            />
            <Button type="submit" className="h-9" disabled={prep.isPending || !prepAbout.trim()}>
              {prep.isPending ? "Preparing…" : "Prep me"}
            </Button>
          </form>
          {prep.data && (
            <div role="status" className="mt-4 rounded-lg border p-3 text-sm">
              <p>{prep.data.summary}</p>
              {prep.data.saves.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs">
                  {prep.data.saves.map((save) => (
                    <li key={save.id}>
                      <a href={`/saves/${save.id}`} className="text-primary hover:underline">
                        {save.title ?? "Untitled save"}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>

        <section className="rounded-xl border bg-card p-5 shadow-sm">
          <h2 className="font-medium tracking-tight">Create a team workspace</h2>
          <form
            className="mt-4 flex gap-2"
            onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault();
              const form = event.currentTarget;
              createTeam.mutate(String(new FormData(form).get("name")));
              form.reset();
            }}
          >
            <Input name="name" required maxLength={80} placeholder="Team name" aria-label="Team name" className="h-9" />
            <Button type="submit" className="h-9" disabled={createTeam.isPending}>
              Create
            </Button>
          </form>
        </section>
      </div>
    </PageBody>
  );
}
