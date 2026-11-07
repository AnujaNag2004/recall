"use client";

import { useCallback, useRef, useState } from "react";
import { streamEvents } from "@/lib/api/client";

export type SourceRef = {
  number: number;
  kind: "save" | "web";
  title: string;
  snippet: string;
  save_id: string | null;
  start_ts: number | null;
  url: string | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceRef[];
  citations?: SourceRef[];
  grounded?: boolean;
  status?: string | null;
  failed?: boolean;
};

type AskEvent =
  | { type: "conversation"; conversation_id: string }
  | { type: "status"; message: string }
  | { type: "sources"; sources: SourceRef[] }
  | { type: "token"; text: string }
  | { type: "done"; citations: SourceRef[]; grounded: boolean; message_id: string }
  | { type: "error"; message: string };

/** One streaming conversation. `endpoint` is either Ask Your Brain or a save's chat. */
export function useAskStream(endpoint: string, extraBody?: Record<string, unknown>) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const conversationId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const load = useCallback((id: string | null, history: ChatMessage[]) => {
    abort.current?.abort();
    conversationId.current = id;
    setMessages(history);
    setBusy(false);
  }, []);

  const send = useCallback(
    async (text: string) => {
      const answerId = crypto.randomUUID();
      setBusy(true);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", content: text },
        { id: answerId, role: "assistant", content: "", status: "Starting" },
      ]);
      const patch = (update: (message: ChatMessage) => ChatMessage) =>
        setMessages((current) => current.map((m) => (m.id === answerId ? update(m) : m)));

      abort.current = new AbortController();
      try {
        await streamEvents<AskEvent>(
          endpoint,
          (event) => {
            if (event.type === "conversation") conversationId.current = event.conversation_id;
            else if (event.type === "status") patch((m) => ({ ...m, status: event.message }));
            else if (event.type === "sources") patch((m) => ({ ...m, sources: event.sources }));
            else if (event.type === "token") {
              patch((m) => ({ ...m, status: null, content: m.content + event.text }));
            } else if (event.type === "done") {
              patch((m) => ({
                ...m,
                content: m.content.trim(),
                status: null,
                citations: event.citations,
                grounded: event.grounded,
              }));
            } else {
              patch((m) => ({ ...m, status: null, failed: true, content: event.message }));
            }
          },
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: abort.current.signal,
            body: JSON.stringify({
              message: text,
              conversation_id: conversationId.current,
              ...extraBody,
            }),
          },
        );
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          patch((m) => ({ ...m, status: null, failed: true, content: (error as Error).message }));
        }
      } finally {
        setBusy(false);
      }
    },
    [endpoint, extraBody],
  );

  return { messages, busy, send, load };
}
