"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircle, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useWorkspaces } from "@/components/app/app-context";
import { Button } from "@/components/ui/button";
import { apiFetch, type Conversation, type Message } from "@/lib/api/client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ChatThread } from "./chat-thread";
import { type ChatMessage, type SourceRef, useAskStream } from "./use-ask";

const selectClass =
  "h-8 rounded-lg border bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function AskView() {
  const { active } = useWorkspaces();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [mode, setMode] = useState("");
  const body = useMemo(() => (mode ? { mode } : undefined), [mode]);
  const { messages, busy, send, load } = useAskStream(`/workspaces/${active?.id}/ask`, body);

  const conversations = useQuery({
    queryKey: ["conversations", active?.id],
    queryFn: () => apiFetch<Conversation[]>(`/workspaces/${active?.id}/conversations`),
    enabled: Boolean(active),
  });

  // Switching workspace starts a clean conversation.
  useEffect(() => {
    load(null, []);
  }, [active?.id, load]);

  const open = async (id: string) => {
    setSelected(id);
    const history = await apiFetch<Message[]>(`/conversations/${id}/messages`);
    load(
      id,
      history.map(
        (m): ChatMessage => ({
          id: m.id,
          role: m.role === "user" ? "user" : "assistant",
          content: m.content,
          citations: m.citations as unknown as SourceRef[],
        }),
      ),
    );
  };

  const submit = async (text: string) => {
    await send(text);
    await queryClient.invalidateQueries({ queryKey: ["conversations", active?.id] });
  };

  return (
    <div className="flex h-full min-h-0">
      <aside className="hidden w-60 shrink-0 flex-col gap-2 border-r p-3 lg:flex">
        <Button
          variant="outline"
          onClick={() => {
            setSelected(null);
            load(null, []);
          }}
        >
          <Plus aria-hidden />
          New question
        </Button>
        <nav aria-label="Past conversations" className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
          {conversations.data?.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              onClick={() => void open(conversation.id)}
              aria-current={selected === conversation.id ? "true" : undefined}
              className={cn(
                "w-full rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-muted",
                selected === conversation.id && "bg-muted",
              )}
            >
              <span className="line-clamp-1">{conversation.title ?? "Conversation"}</span>
              <span className="text-xs text-muted-foreground">
                {formatDate(conversation.updated_at)}
              </span>
            </button>
          ))}
        </nav>
      </aside>
      <div className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col px-4 py-4 sm:px-6">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h1 className="text-lg font-semibold tracking-tight">Ask Your Brain</h1>
          <select
            aria-label="Search within a mode"
            className={selectClass}
            value={mode}
            onChange={(event) => setMode(event.target.value)}
          >
            <option value="">All modes</option>
            <option value="life">Life</option>
            <option value="study">Study</option>
            <option value="work">Work</option>
          </select>
        </div>
        <ChatThread
          messages={messages}
          busy={busy}
          onSend={(text) => void submit(text)}
          placeholder="Ask anything you've saved"
          empty={
            <div className="py-16 text-center">
              <MessageCircle className="mx-auto size-6 text-muted-foreground" aria-hidden />
              <p className="mt-3 font-medium">What do you want to remember?</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Try &ldquo;what did the client say about pricing?&rdquo; Every answer cites its source.
              </p>
            </div>
          }
        />
      </div>
    </div>
  );
}
