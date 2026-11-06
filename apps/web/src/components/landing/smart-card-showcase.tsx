"use client";

import { Check, CircleAlert, Play } from "lucide-react";
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { Container, Panel, SampleTag, SectionHeading } from "./primitives";
import { formatTimestamp, sampleSave } from "./sample-save";

const VIDEO_LENGTH_SECONDS = 902;

function Timestamp({ seconds, onSeek }: { seconds: number; onSeek: (seconds: number) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSeek(seconds)}
      aria-label={`Jump to ${formatTimestamp(seconds)} in the video`}
      className="rounded font-mono text-xs text-primary tabular-nums hover:underline"
    >
      {formatTimestamp(seconds)}
    </button>
  );
}

function Player({ time, onSeek }: { time: number; onSeek: (seconds: number) => void }) {
  return (
    <div>
      <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-xl bg-muted">
        <span className="flex size-12 items-center justify-center rounded-full bg-background shadow-sm">
          <Play className="ml-0.5 size-5" aria-hidden />
        </span>
        <span className="absolute right-3 bottom-3 rounded bg-background/90 px-1.5 py-0.5 font-mono text-xs tabular-nums">
          {formatTimestamp(time)} / {formatTimestamp(VIDEO_LENGTH_SECONDS)}
        </span>
        <div className="absolute inset-x-0 bottom-0 h-1 bg-foreground/10">
          <div
            className="h-full bg-primary transition-[width] duration-500"
            style={{ width: `${(time / VIDEO_LENGTH_SECONDS) * 100}%` }}
          />
        </div>
      </div>
      <p className="mt-4 text-sm font-medium tracking-tight">{sampleSave.title}</p>
      <p className="text-xs text-muted-foreground">{sampleSave.source}</p>
      <h3 className="mt-5 text-xs font-medium text-muted-foreground">Transcript</h3>
      <ul className="mt-2 space-y-1">
        {sampleSave.transcript.map((line) => (
          <li key={line.at}>
            <button
              type="button"
              onClick={() => onSeek(line.at)}
              aria-current={line.at === time ? "true" : undefined}
              className={cn(
                "flex w-full gap-3 rounded-lg px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted",
                line.at === time ? "bg-muted" : "text-muted-foreground",
              )}
            >
              <span className="mt-0.5 font-mono text-xs text-primary tabular-nums">
                {formatTimestamp(line.at)}
              </span>
              <span>{line.text}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SummaryTab() {
  return (
    <div>
      <p className="leading-relaxed">{sampleSave.summary}</p>
      <h3 className="mt-6 text-xs font-medium text-muted-foreground">Key points</h3>
      <ul className="mt-2 space-y-2">
        {sampleSave.keyPoints.map((point) => (
          <li key={point} className="flex gap-2 text-muted-foreground">
            <span className="mt-2 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
            {point}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ResourcesTab({ onSeek }: { onSeek: (seconds: number) => void }) {
  return (
    <ul className="divide-y">
      {sampleSave.resources.map((resource) => (
        <li key={resource.name} className="flex gap-3 py-3 first:pt-0 last:pb-0">
          <span
            aria-hidden
            className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-xs font-semibold"
          >
            {resource.verified ? resource.name[0] : "?"}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className="font-medium">{resource.name}</span>
              <span className="text-xs text-muted-foreground">{resource.pricing}</span>
            </div>
            <p className="text-xs text-muted-foreground">{resource.note}</p>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
              {resource.verified ? (
                <span className="flex items-center gap-1 font-medium">
                  <Check className="size-3 text-primary" aria-hidden />
                  {resource.domain}
                </span>
              ) : (
                <span className="flex items-center gap-1 font-medium">
                  <CircleAlert className="size-3" aria-hidden />
                  Unverified
                </span>
              )}
              <span className="text-muted-foreground tabular-nums">
                {Math.round(resource.confidence * 100)}% confidence
              </span>
              <Timestamp seconds={resource.at} onSeek={onSeek} />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ActionsTab() {
  return (
    <div>
      <p className="text-muted-foreground">Nothing is added to your tasks until you approve it.</p>
      <ul className="mt-4 space-y-2">
        {sampleSave.actions.map((action) => (
          <li key={action.title}>
            <label
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors hover:bg-muted/60",
                action.micro && "border-primary/30 bg-primary/5",
              )}
            >
              <input
                type="checkbox"
                defaultChecked={action.micro}
                className="mt-0.5 size-4 accent-[var(--primary)]"
              />
              <span>
                <span className="block font-medium">{action.title}</span>
                <span className="block text-xs text-muted-foreground">{action.detail}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ChatTab({ onSeek }: { onSeek: (seconds: number) => void }) {
  return (
    <div className="space-y-3">
      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-muted px-3.5 py-2">
        When should I use BFS instead of Dijkstra?
      </p>
      <div className="max-w-[92%] leading-relaxed">
        <p>
          Use BFS when every edge costs the same, because it already finds the shortest path. Reach
          for Dijkstra once edges have different non-negative weights.
        </p>
        <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          From this save at <Timestamp seconds={192} onSeek={onSeek} />
        </p>
      </div>
    </div>
  );
}

export function SmartCardShowcase() {
  const [time, setTime] = useState(sampleSave.transcript[0].at);

  return (
    <section className="py-20 sm:py-28">
      <Container>
        <SectionHeading
          eyebrow="Smart Cards"
          title="Every save becomes something you can use."
          lead="The original content sits next to a summary, checked links, a plan and a chat. Try the tabs."
        />
        <Panel className="reveal mt-12 grid grid-cols-1 overflow-hidden md:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
          <div className="border-b p-4 sm:p-6 md:border-r md:border-b-0">
            <Player time={time} onSeek={setTime} />
          </div>
          <div className="min-w-0 p-4 sm:p-6">
            <Tabs defaultValue="summary" className="gap-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <TabsList className="grid w-full grid-cols-4 group-data-horizontal/tabs:h-10 sm:w-auto">
                  {["Summary", "Resources", "Actions", "Chat"].map((tab) => (
                    <TabsTrigger key={tab} value={tab.toLowerCase()} className="px-1 text-xs sm:px-3 sm:text-sm">
                      {tab}
                    </TabsTrigger>
                  ))}
                </TabsList>
                <SampleTag />
              </div>
              {/* A shared minimum height keeps the panel still when switching tabs. */}
              <div className="min-h-80">
                <TabsContent value="summary">
                  <SummaryTab />
                </TabsContent>
                <TabsContent value="resources">
                  <ResourcesTab onSeek={setTime} />
                </TabsContent>
                <TabsContent value="actions">
                  <ActionsTab />
                </TabsContent>
                <TabsContent value="chat">
                  <ChatTab onSeek={setTime} />
                </TabsContent>
              </div>
            </Tabs>
          </div>
        </Panel>
      </Container>
    </section>
  );
}
