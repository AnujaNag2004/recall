import { ArrowRight } from "lucide-react";
import { site } from "@/lib/site";
import { Container, CtaLink } from "./primitives";
import { SmartCardPreview } from "./smart-card-preview";

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* A single soft glow behind the card: the only decoration in the hero. */}
      <div
        aria-hidden
        className="pointer-events-none absolute top-[-10%] right-[-20%] size-[720px] rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklch,var(--primary)_16%,transparent),transparent)]"
      />
      <Container className="relative grid grid-cols-1 items-center gap-14 pt-14 pb-20 sm:pt-20 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:gap-12 lg:pt-24 lg:pb-32">
        <div>
          <h1 className="text-5xl leading-[1.02] font-semibold tracking-[-0.035em] text-balance sm:text-7xl">
            Stop saving.
            <br />
            <span className="text-primary">Start doing.</span>
          </h1>
          <p
            className="rise mt-6 max-w-lg text-lg leading-relaxed text-pretty text-muted-foreground sm:text-xl"
            style={{ "--rise-delay": "80ms" } as React.CSSProperties}
          >
            Recall turns the posts, videos and docs you save into small next steps, brings them
            back at the right moment, and shows whether they changed anything.
          </p>
          <div
            className="rise mt-8 flex flex-wrap gap-3"
            style={{ "--rise-delay": "160ms" } as React.CSSProperties}
          >
            <CtaLink href={site.routes.signUp}>
              Get started free
              <ArrowRight aria-hidden />
            </CtaLink>
            <CtaLink href={site.routes.demo} variant="outline">
              Try the live demo
            </CtaLink>
          </div>
        </div>
        <div className="rise" style={{ "--rise-delay": "200ms" } as React.CSSProperties}>
          <SmartCardPreview />
        </div>
      </Container>
    </section>
  );
}
