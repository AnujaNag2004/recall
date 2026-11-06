"use client";

import { RotateCcw } from "lucide-react";
import { useInView, useReducedMotion } from "motion/react";
import * as m from "motion/react-m";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Container, Panel, SampleTag, SectionHeading } from "./primitives";

const engineSteps = [
  {
    title: "Asks why",
    body: "A two-second prompt on save: learn, try, buy, cook, or just vibes. Skip it and the agent infers your intent.",
  },
  {
    title: "Shrinks the task",
    body: "Your intent becomes the smallest concrete first step, with a suggested time you can edit or dismiss.",
  },
  {
    title: "Shows up at the right time",
    body: "An exam tomorrow or a client call at 3 brings back the saves that matter for it.",
  },
  {
    title: "Tells you the truth",
    body: "A weekly reflection spots your patterns, and sometimes suggests saving less.",
  },
];

/** Sample numbers: how much a person saves in each area, and how much they act on. */
const categories = [
  { name: "Cooking", saved: 6, acted: 5 },
  { name: "Study", saved: 9, acted: 4 },
  { name: "Fitness", saved: 11, acted: 0 },
];
const MOST_SAVED = Math.max(...categories.map((category) => category.saved));

type Outcome = "done" | "notYet" | "letGo";

const outcomes: Record<Outcome, { acted: number; total: number; prompt: string; reply: string }> = {
  done: {
    acted: 10,
    total: 26,
    prompt: "Solve 1 graph problem",
    reply: "Logged. Next up: step through BFS on VisuAlgo, tomorrow.",
  },
  notYet: {
    acted: 9,
    total: 26,
    prompt: "Read one problem statement",
    reply: "No problem. Here's a smaller step: 2 minutes, same time tomorrow.",
  },
  letGo: {
    acted: 9,
    total: 25,
    prompt: "Solve 1 graph problem",
    reply: "Archived, no guilt. Fewer open promises also lifts your score.",
  },
};
const START = { acted: 9, total: 26, prompt: "Solve 1 graph problem" };

function ScoreRing({ acted, total }: { acted: number; total: number }) {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const reducedMotion = useReducedMotion();
  const ratio = acted / total;

  return (
    <div className="relative size-36 shrink-0">
      <svg ref={ref} viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden>
        <circle cx="60" cy="60" r="52" fill="none" strokeWidth="8" className="stroke-muted" />
        <m.circle
          cx="60"
          cy="60"
          r="52"
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          className="stroke-primary"
          initial={false}
          animate={{ pathLength: inView || reducedMotion ? ratio : 0.001 }}
          transition={{ duration: reducedMotion ? 0 : 0.9, ease: [0.2, 0.7, 0.2, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tracking-tight tabular-nums">
          {Math.round(ratio * 100)}%
        </span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {acted} of {total} saves
        </span>
      </div>
    </div>
  );
}

export function SaveToAction() {
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const state = outcome ? outcomes[outcome] : START;

  return (
    <section className="border-y bg-muted/40 py-20 sm:py-28">
      <Container className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-16">
        <div>
          <SectionHeading
            eyebrow="The Save-to-Action Engine"
            title="The only metric that matters: did you do it?"
            lead="Recall measures what your saves led to, not how many you have. Then it helps you close the gap."
          />
          <dl className="reveal mt-10 grid gap-6 sm:grid-cols-2">
            {engineSteps.map((step) => (
              <div key={step.title}>
                <dt className="font-medium tracking-tight">{step.title}</dt>
                <dd className="mt-1 text-sm leading-relaxed text-muted-foreground">{step.body}</dd>
              </div>
            ))}
          </dl>
        </div>

        <Panel className="reveal self-start p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-medium tracking-tight">Your Save-to-Action score</h3>
            <SampleTag />
          </div>

          <div className="mt-6 flex flex-col items-center gap-6 sm:flex-row sm:items-center">
            <ScoreRing acted={state.acted} total={state.total} />
            <div className="w-full min-w-0 flex-1">
              <ul className="space-y-3">
                {categories.map((category) => (
                  <li key={category.name}>
                    <div className="flex items-baseline justify-between text-xs">
                      <span className="font-medium">{category.name}</span>
                      <span className="text-muted-foreground tabular-nums">
                        {category.acted} of {category.saved} acted on
                      </span>
                    </div>
                    {/* Track length is what you saved; the filled part is what you did. */}
                    <div
                      className="mt-1.5 h-1.5 rounded-full bg-muted"
                      style={{ width: `${(category.saved / MOST_SAVED) * 100}%` }}
                    >
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${(category.acted / category.saved) * 100}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted-foreground">
                You save fitness. You act on cooking.
              </p>
            </div>
          </div>

          <div className="mt-6 rounded-xl border bg-background p-4">
            <p className="text-xs text-muted-foreground">Yesterday you planned to:</p>
            <p className="mt-1 font-medium">{state.prompt}</p>

            {outcome ? (
              <div className="mt-3">
                <p aria-live="polite" className="text-sm text-muted-foreground">
                  {outcomes[outcome].reply}
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2 -ml-2 text-muted-foreground"
                  onClick={() => setOutcome(null)}
                >
                  <RotateCcw aria-hidden />
                  Try another answer
                </Button>
              </div>
            ) : (
              <div className="mt-3">
                <p id="did-you-do-it" className="text-sm font-medium">
                  Did you do it?
                </p>
                <div
                  role="group"
                  aria-labelledby="did-you-do-it"
                  className="mt-2 flex flex-wrap gap-2"
                >
                  <Button onClick={() => setOutcome("done")}>Done</Button>
                  <Button variant="outline" onClick={() => setOutcome("notYet")}>
                    Not yet
                  </Button>
                  <Button variant="ghost" onClick={() => setOutcome("letGo")}>
                    Let go
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Panel>
      </Container>
    </section>
  );
}
