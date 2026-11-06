import { Check, Link2, Square } from "lucide-react";
import type { ReactNode } from "react";
import { Container, Panel, SectionHeading } from "./primitives";

function CaptureDemo() {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2">
        <Link2 className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
        <span className="loop-type truncate font-mono text-xs">youtube.com/watch?v=graphs</span>
      </div>
      <div className="loop-2 flex flex-wrap gap-1.5">
        {["Learn", "Try", "Reference"].map((intent, index) => (
          <span
            key={intent}
            className={
              index === 0
                ? "rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary"
                : "rounded-md border px-2 py-1 text-xs text-muted-foreground"
            }
          >
            {intent}
          </span>
        ))}
      </div>
    </div>
  );
}

function UnderstandDemo() {
  const steps = ["Transcribed", "Summarized", "Links verified"];
  return (
    <ul className="space-y-2 text-sm">
      {steps.map((step, index) => (
        <li key={step} className={`loop-${index + 1} flex items-center gap-2`}>
          <Check className="size-4 text-primary" aria-hidden />
          {step}
        </li>
      ))}
    </ul>
  );
}

function ActDemo() {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm">
        <Square className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="truncate">Solve 1 graph problem</span>
      </div>
      <p className="loop-2 pl-1 text-xs text-muted-foreground">Tonight, 9:00 pm</p>
      <p className="loop-3 flex items-center gap-1.5 pl-1 text-xs font-medium text-primary">
        <Check className="size-3.5" aria-hidden />
        Did it. Score updated.
      </p>
    </div>
  );
}

const steps: { title: string; body: string; demo: ReactNode }[] = [
  {
    title: "Capture",
    body: "Paste a link, drop a file or type a note. Videos, posts, PDFs, screenshots, voice notes and emails all go to one place.",
    demo: <CaptureDemo />,
  },
  {
    title: "Understand",
    body: "A team of agents transcribes, summarizes and pulls out every tool and book mentioned, with links checked against real search results.",
    demo: <UnderstandDemo />,
  },
  {
    title: "Act",
    body: "You get the smallest useful next step at a sensible time. Recall follows up later, and comes back to your save when it's relevant.",
    demo: <ActDemo />,
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-20 sm:py-28">
      <Container>
        <SectionHeading eyebrow="How it works" title="From saved to done, in three steps." />
        <ol className="mt-12 grid gap-4 md:grid-cols-3">
          {steps.map((step, index) => (
            <li key={step.title} className="reveal">
              <Panel className="flex h-full flex-col p-6">
                <div className="h-28">{step.demo}</div>
                <h3 className="mt-6 text-lg font-semibold tracking-tight">
                  <span className="mr-2 font-mono text-sm font-normal text-muted-foreground">
                    {index + 1}
                  </span>
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </Panel>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}
