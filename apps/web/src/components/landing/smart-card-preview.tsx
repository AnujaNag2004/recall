"use client";

import { Check, Clock, Link2, Play, Sparkles } from "lucide-react";
import { useInView, useReducedMotion } from "motion/react";
import * as m from "motion/react-m";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Panel } from "./primitives";
import { sampleSave } from "./sample-save";

/** The ingestion graph's visible stages, in the order the card builds itself. */
const stages = [
  "Reading the link",
  "Writing the summary",
  "Finding resources",
  "Planning a next step",
  "Ready",
];
const FINAL_STAGE = stages.length - 1;
const STAGE_MS = 1500;
const HOLD_FINISHED_MS = 5500;

/** A skeleton and its content stacked in one grid cell, so nothing shifts on reveal. */
function Slot({ show, skeleton, children }: { show: boolean; skeleton: ReactNode; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 [&>*]:col-start-1 [&>*]:row-start-1">
      <m.div
        initial={false}
        animate={{ opacity: show ? 0 : 1 }}
        transition={{ duration: 0.25 }}
        aria-hidden
      >
        {skeleton}
      </m.div>
      <m.div
        initial={false}
        animate={{ opacity: show ? 1 : 0, y: show ? 0 : 6 }}
        transition={{ duration: 0.4, ease: [0.2, 0.7, 0.2, 1] }}
      >
        {children}
      </m.div>
    </div>
  );
}

function SkeletonLine({ className }: { className?: string }) {
  return <div className={cn("h-3 rounded-full bg-muted", className)} />;
}

export function SmartCardPreview() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref);
  const reducedMotion = useReducedMotion();
  const [stage, setStage] = useState(0);

  useEffect(() => {
    if (!inView || reducedMotion) return;
    const timer = setTimeout(
      () => setStage((current) => (current === FINAL_STAGE ? 0 : current + 1)),
      stage === FINAL_STAGE ? HOLD_FINISHED_MS : STAGE_MS,
    );
    return () => clearTimeout(timer);
  }, [stage, inView, reducedMotion]);

  // With reduced motion, simply show the finished card.
  const current = reducedMotion ? FINAL_STAGE : stage;
  const finished = current === FINAL_STAGE;

  return (
    <div
      ref={ref}
      role="img"
      aria-label={`Example Smart Card for a saved video, "${sampleSave.title}", with a summary, resources and next steps.`}
    >
      <Panel className="overflow-hidden shadow-lg shadow-primary/5">
        <div className="flex items-center gap-2 border-b px-4 py-3 text-sm">
          <Link2 className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">
            {sampleSave.url}
          </span>
          <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium">
            {finished ? (
              <Check className="size-3.5 text-primary" aria-hidden />
            ) : (
              <span className="size-1.5 animate-pulse rounded-full bg-primary" aria-hidden />
            )}
            {stages[current]}
          </span>
        </div>

        <div className="space-y-5 p-4 sm:p-5">
          <div className="flex gap-3">
            <div className="flex aspect-video w-24 shrink-0 items-center justify-center rounded-lg bg-muted">
              <Play className="size-4 text-muted-foreground" aria-hidden />
            </div>
            <div className="min-w-0">
              <p className="font-medium tracking-tight">{sampleSave.title}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {sampleSave.source} · {sampleSave.mode}
              </p>
            </div>
          </div>

          <Slot
            show={current >= 1}
            skeleton={
              <div className="space-y-2 pt-1">
                <SkeletonLine />
                <SkeletonLine className="w-11/12" />
                <SkeletonLine className="w-3/5" />
              </div>
            }
          >
            <p className="text-sm leading-relaxed text-muted-foreground">{sampleSave.summary}</p>
          </Slot>

          <Slot
            show={current >= 2}
            skeleton={
              <div className="flex gap-2">
                <SkeletonLine className="h-7 w-24" />
                <SkeletonLine className="h-7 w-28" />
                <SkeletonLine className="h-7 w-20" />
              </div>
            }
          >
            <div className="flex flex-wrap gap-2">
              {sampleSave.resources
                .filter((resource) => resource.verified)
                .map((resource) => (
                  <span
                    key={resource.name}
                    className="inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs"
                  >
                    <span
                      aria-hidden
                      className="flex size-4 items-center justify-center rounded bg-muted text-[10px] font-semibold"
                    >
                      {resource.name[0]}
                    </span>
                    {resource.domain}
                  </span>
                ))}
            </div>
          </Slot>

          <Slot
            show={current >= 3}
            skeleton={
              <div className="space-y-2">
                <SkeletonLine className="h-14 w-full rounded-xl" />
                <SkeletonLine className="h-9 w-full rounded-xl" />
              </div>
            }
          >
            <div className="space-y-2">
              <div className="rounded-xl border border-primary/30 bg-primary/5 p-3">
                <p className="flex items-center gap-1.5 text-xs font-medium text-primary">
                  <Sparkles className="size-3.5" aria-hidden />
                  Smallest next step
                </p>
                <p className="mt-1 text-sm font-medium">{sampleSave.actions[0].title}</p>
                <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="size-3" aria-hidden />
                  {sampleSave.actions[0].detail}
                </p>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-sm">
                <span className="truncate">{sampleSave.actions[1].title}</span>
                <span className="shrink-0 text-xs text-muted-foreground">Tomorrow</span>
              </div>
            </div>
          </Slot>
        </div>
      </Panel>
    </div>
  );
}
