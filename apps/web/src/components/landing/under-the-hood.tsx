import { ChevronRight } from "lucide-react";
import { Fragment } from "react";
import { Container, SectionHeading } from "./primitives";

const pipeline = [
  "fetch",
  "sanitize",
  "classify",
  "summarize",
  "embed",
  "extract_entities",
  "verify_links",
  "plan_actions",
  "micro_commit",
];

const pillars = [
  {
    title: "Agents",
    body: "LangGraph workflows with typed state, retries, and structured outputs validated by Pydantic.",
  },
  {
    title: "Agentic RAG",
    body: "Vector and full-text search fused with RRF. It grades what it finds and rewrites weak queries before answering.",
  },
  {
    title: "Guardrails",
    body: "Saved content is treated as untrusted data. Links must come from real search results. Outside actions wait for your approval.",
  },
  {
    title: "Evals",
    body: "Labeled datasets for link accuracy, RAG faithfulness, action extraction and classification.",
  },
];

const stack = "Next.js · FastAPI · LangGraph · Postgres + pgvector · Row-level security · Gemini · Groq";

export function UnderTheHood() {
  return (
    <section className="border-y bg-muted/40 py-20 sm:py-28">
      <Container>
        <SectionHeading
          eyebrow="Under the hood"
          title="Built like a system, not a wrapper."
          lead="For the engineers reading: this is how a save moves through the ingestion graph."
        />
        <ol
          aria-label="Ingestion graph stages"
          className="reveal mt-10 flex flex-wrap items-center gap-x-1.5 gap-y-2 font-mono text-xs"
        >
          {pipeline.map((node, index) => (
            <Fragment key={node}>
              <li className="rounded-md border bg-background px-2 py-1">{node}</li>
              {index < pipeline.length - 1 && (
                <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden />
              )}
            </Fragment>
          ))}
        </ol>
        <dl className="reveal mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {pillars.map((pillar) => (
            <div key={pillar.title} className="border-t pt-4">
              <dt className="font-semibold tracking-tight">{pillar.title}</dt>
              <dd className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{pillar.body}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-10 font-mono text-xs leading-relaxed text-muted-foreground">{stack}</p>
      </Container>
    </section>
  );
}
