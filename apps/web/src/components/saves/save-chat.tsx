"use client";

import { ChatThread } from "@/components/ask/chat-thread";
import { useAskStream } from "@/components/ask/use-ask";

export function SaveChat({ saveId, onSeek }: { saveId: string; onSeek: (s: number) => void }) {
  const { messages, busy, send } = useAskStream(`/saves/${saveId}/chat`);
  return (
    <ChatThread
      compact
      messages={messages}
      busy={busy}
      onSend={(text) => void send(text)}
      onSeek={onSeek}
      placeholder="Ask about this save"
      empty={
        <p className="text-sm text-muted-foreground">
          Ask anything about this save. Answers come only from its content.
        </p>
      }
    />
  );
}
