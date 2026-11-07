"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, KeyRound, Trash2 } from "lucide-react";
import Link from "next/link";
import { type FormEvent, type ReactNode, useState } from "react";
import { toast } from "sonner";
import { signOut, useMe, useWorkspaces } from "@/components/app/app-context";
import { PageBody, PageHeader } from "@/components/app/page-states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  apiDownload,
  apiFetch,
  apiJson,
  type ApiKey,
  type ApiKeyCreated,
  type Usage,
} from "@/lib/api/client";
import { formatDate } from "@/lib/format";

function Section({ title, lead, children }: { title: string; lead?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border bg-card p-5 shadow-sm">
      <h2 className="font-medium tracking-tight">{title}</h2>
      {lead && <p className="mt-1 text-sm text-muted-foreground">{lead}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Profile() {
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (body: object) => apiJson("/me", "PATCH", body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      toast.success("Saved.");
    },
    onError: (error) => toast.error(error.message),
  });
  if (!me) return null;
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    save.mutate({ name: data.get("name"), timezone: data.get("timezone") });
  };
  return (
    <Section title="Profile">
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="name">Name</Label>
          <Input id="name" name="name" required maxLength={120} defaultValue={me.user.name ?? ""} className="h-10" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="timezone">Time zone</Label>
          <Input
            id="timezone"
            name="timezone"
            required
            maxLength={64}
            defaultValue={me.user.timezone}
            className="h-10"
          />
        </div>
        <p className="text-sm text-muted-foreground sm:col-span-2">Signed in as {me.user.email}</p>
        <div>
          <Button type="submit" disabled={save.isPending}>
            Save changes
          </Button>
        </div>
      </form>
    </Section>
  );
}

function UsagePanel() {
  const usage = useQuery({ queryKey: ["usage"], queryFn: () => apiFetch<Usage>("/me/usage") });
  if (!usage.data) return null;
  const { used_today: used, daily_cap: cap } = usage.data;
  return (
    <Section title="AI usage today" lead="A daily limit keeps the service free for everyone.">
      <p className="text-sm tabular-nums">
        {used} of {cap} actions
      </p>
      <div
        role="progressbar"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={cap}
        aria-label="AI actions used today"
        className="mt-2 h-2 rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${Math.min((used / Math.max(cap, 1)) * 100, 100)}%` }}
        />
      </div>
    </Section>
  );
}

function GoogleCalendar() {
  const queryClient = useQueryClient();
  const { active } = useWorkspaces();
  const status = useQuery({
    queryKey: ["google-status"],
    queryFn: () => apiFetch<{ configured: boolean; connected: boolean }>("/integrations/google/status"),
  });
  const connect = useMutation({
    mutationFn: () => apiJson<{ url: string }>("/integrations/google/connect", "POST"),
    onSuccess: (result) => window.location.assign(result.url),
    onError: (error) => toast.error(error.message),
  });
  const sync = useMutation({
    mutationFn: () =>
      apiJson<{ synced: number }>(`/workspaces/${active?.id}/calendar/google/sync`, "POST"),
    onSuccess: (result) => toast.success(`Synced ${result.synced} events.`),
    onError: (error) => toast.error(error.message),
  });
  const disconnect = useMutation({
    mutationFn: () => apiFetch("/integrations/google", { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["google-status"] }),
    onError: (error) => toast.error(error.message),
  });
  return (
    <Section
      title="Google Calendar"
      lead="Reads your upcoming events for just-in-time recall. Events are only created when you ask."
    >
      {!status.data?.configured ? (
        <p className="text-sm text-muted-foreground">
          Not available on this server yet. You can still export an .ics file from Tasks.
        </p>
      ) : status.data.connected ? (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={sync.isPending || !active} onClick={() => sync.mutate()}>
            Sync now
          </Button>
          <Button variant="ghost" disabled={disconnect.isPending} onClick={() => disconnect.mutate()}>
            Disconnect
          </Button>
        </div>
      ) : (
        <Button variant="outline" disabled={connect.isPending} onClick={() => connect.mutate()}>
          Connect Google Calendar
        </Button>
      )}
    </Section>
  );
}

function ApiKeys() {
  const queryClient = useQueryClient();
  const [created, setCreated] = useState<string | null>(null);
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: () => apiFetch<ApiKey[]>("/api-keys") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["api-keys"] });
  const create = useMutation({
    mutationFn: (label: string) => apiJson<ApiKeyCreated>("/api-keys", "POST", { label }),
    onSuccess: async (result) => {
      setCreated(result.key);
      await refresh();
    },
    onError: (error) => toast.error(error.message),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiFetch(`/api-keys/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
    onError: (error) => toast.error(error.message),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    create.mutate(String(new FormData(form).get("label")));
    form.reset();
  };
  return (
    <Section title="API keys" lead="For the Recall MCP server and your own tools. A key acts as you.">
      {created && (
        <div role="status" className="mb-4 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
          <p className="font-medium">Copy this now. You won&apos;t see it again.</p>
          <div className="mt-2 flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate font-mono text-xs">{created}</code>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void navigator.clipboard.writeText(created).then(() => toast.success("Copied."))}
            >
              <Copy aria-hidden />
              Copy
            </Button>
          </div>
        </div>
      )}
      <form onSubmit={submit} className="flex gap-2">
        <Input name="label" required maxLength={80} placeholder="Key name, like Laptop" aria-label="Key name" className="h-10" />
        <Button type="submit" className="h-10" disabled={create.isPending}>
          <KeyRound aria-hidden />
          Create
        </Button>
      </form>
      {(keys.data?.length ?? 0) > 0 && (
        <ul className="mt-4 divide-y rounded-lg border">
          {keys.data?.map((key) => (
            <li key={key.id} className="flex items-center justify-between gap-3 p-3 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium">{key.label}</p>
                <p className="text-xs text-muted-foreground">
                  {key.last_used_at ? `Last used ${formatDate(key.last_used_at)}` : "Never used"}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground"
                aria-label={`Revoke ${key.label}`}
                onClick={() => remove.mutate(key.id)}
              >
                <Trash2 aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function YourData() {
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const remove = useMutation({
    mutationFn: () => apiJson("/me", "DELETE", { confirm: typed }),
    onSuccess: () => void signOut(),
    onError: (error) => toast.error(error.message),
  });
  return (
    <Section title="Your data">
      <Button
        variant="outline"
        onClick={() =>
          void apiDownload("/me/export", "recall-export.json").catch((error: Error) =>
            toast.error(error.message),
          )
        }
      >
        <Download aria-hidden />
        Export as JSON
      </Button>
      <div className="mt-6 border-t pt-4">
        <h3 className="text-sm font-medium">Delete account</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          This permanently deletes your account, your saves, and any team workspaces you own. It
          can&apos;t be undone.
        </p>
        {confirming ? (
          <div className="mt-3 space-y-2">
            <Label htmlFor="confirm-delete">
              Type <span className="font-mono">delete my account</span> to confirm
            </Label>
            <Input
              id="confirm-delete"
              value={typed}
              autoComplete="off"
              onChange={(event) => setTyped(event.target.value)}
              className="h-10"
            />
            <div className="flex gap-2">
              <Button
                variant="destructive"
                disabled={typed !== "delete my account" || remove.isPending}
                onClick={() => remove.mutate()}
              >
                Delete everything
              </Button>
              <Button variant="ghost" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="destructive" className="mt-3" onClick={() => setConfirming(true)}>
            Delete my account
          </Button>
        )}
      </div>
    </Section>
  );
}

export function SettingsView() {
  const { active } = useWorkspaces();
  const canAdminister = active?.role === "owner" || active?.role === "admin";
  return (
    <PageBody className="max-w-3xl">
      <PageHeader title="Settings" />
      <div className="mt-6 space-y-4">
        <Section title="Workspace" lead={active ? `You're in ${active.name}.` : undefined}>
          <div className="flex flex-wrap gap-2 text-sm">
            <Link href="/settings/workspace" className="font-medium text-primary hover:underline">
              Members and invites
            </Link>
            {canAdminister && (
              <Link href="/settings/agent-runs" className="font-medium text-primary hover:underline">
                Agent runs
              </Link>
            )}
          </div>
        </Section>
        <Profile />
        <UsagePanel />
        <GoogleCalendar />
        <ApiKeys />
        <YourData />
      </div>
    </PageBody>
  );
}
