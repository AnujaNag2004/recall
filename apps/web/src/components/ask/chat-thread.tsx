"use client";

import { CircleAlert, Loader2, Send } from "lucide-react";
import Link from "next/link";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { formatTimestamp } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AnswerText } from "./answer-text";
import type { ChatMessage, SourceRef } from "./use-ask";

function SourceLink({
  source,
  onSeek,
}: {
  source: SourceRef;
  onSeek?: (seconds: number) => void;
}) {
  if (source.kind === "web" && source.url) {
    return (
      <a href={source.url} target="_blank" rel="noopener noreferrer nofollow" className="font-medium hover:underline">
        {source.title}
      </a>
    );
  }
  if (onSeek && source.start_ts !== null) {
    return (
      <button type="button" onClick={() => onSeek(source.start_ts as number)} className="text-left font-medium hover:underline">
        {source.title} at {formatTimestamp(source.start_ts)}
      </button>
    );
  }
  return (
    <Link href={`/saves/${source.save_id}`} className="font-medium hover:underline">
      {source.title}
    </Link>
  );
}

export function ChatThread({
  messages,
  busy,
  onSend,
  placeholder,
  empty,
  onSeek,
  compact,
}: {
  messages: ChatMessage[];
  busy: boolean;
  onSend: (text: string) => void;
  placeholder: string;
  empty?: ReactNode;
  onSeek?: (seconds: number) => void;
  compact?: boolean;
}) {
  const [text, setText] = useState("");
  const [openSource, setOpenSource] = useState<SourceRef | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest" });
  }, [messages]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    setText("");
    onSend(message);
  };

  return (
    <div className={cn("flex min-h-0 flex-col", compact ? "h-[28rem]" : "flex-1")}>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto pb-4" aria-live="polite">
        {messages.length === 0 && empty}
        {messages.map((message) =>
          message.role === "user" ? (
            <p
              key={message.id}
              className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-muted px-3.5 py-2 text-sm whitespace-pre-wrap"
            >
              {message.content}
            </p>
          ) : (
            <div key={message.id} className="max-w-[92%] text-sm leading-relaxed">
              {message.status && (
                <p role="status" className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  {message.status}…
                </p>
              )}
              {message.failed ? (
                <p role="alert" className="flex items-start gap-2 text-destructive">
                  <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  {message.content}
                </p>
              ) : (
                <AnswerText
                  content={message.content}
                  sources={message.sources ?? message.citations}
                  onOpen={setOpenSource}
                />
              )}
              {message.grounded === false && (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <CircleAlert className="size-3.5" aria-hidden />
                  Parts of this may go beyond your sources, so check them before relying on it.
                </p>
              )}
              {(message.citations?.length ?? 0) > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
                  {message.citations?.map((source) => (
                    <li key={source.number}>
                      <span className="tabular-nums">{source.number}. </span>
                      <SourceLink source={source} onSeek={onSeek} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ),
        )}
        <div ref={bottom} />
      </div>

      {openSource && (
        <aside aria-label="Source" className="mb-3 rounded-xl border bg-card p-3 text-xs">
          <div className="flex items-start justify-between gap-3">
            <SourceLink source={openSource} onSeek={onSeek} />
            <button
              type="button"
              onClick={() => setOpenSource(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>
          <p className="mt-1.5 text-muted-foreground">{openSource.snippet}</p>
        </aside>
      )}

      <form onSubmit={submit} className="flex gap-2">
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          className="h-10 min-w-0 flex-1 rounded-lg border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button type="submit" size="icon" className="size-10" aria-label="Send" disabled={busy || !text.trim()}>
          <Send aria-hidden />
        </Button>
      </form>
    </div>
  );
}
