import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Container({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("mx-auto w-full max-w-6xl px-4 sm:px-6", className)} {...props} />;
}

export function Wordmark({ className, markOnly = false }: { className?: string; markOnly?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
        <circle
          cx="12"
          cy="12"
          r="9"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          pathLength="100"
          strokeDasharray="78 22"
          transform="rotate(-50 12 12)"
        />
        <circle cx="12" cy="12" r="3.5" className="fill-primary" />
      </svg>
      {!markOnly && "Recall"}
    </span>
  );
}

type CtaLinkProps = ComponentProps<typeof Link> & {
  variant?: "default" | "outline" | "ghost";
  size?: "md" | "lg";
};

export function CtaLink({ variant = "default", size = "lg", className, ...props }: CtaLinkProps) {
  return (
    <Link
      className={cn(
        buttonVariants({ variant }),
        size === "lg" ? "h-11 rounded-xl px-5 text-[15px]" : "h-9 rounded-lg px-3.5",
        className,
      )}
      {...props}
    />
  );
}

export function SectionHeading({
  eyebrow,
  title,
  lead,
  className,
}: {
  eyebrow: string;
  title: ReactNode;
  lead?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("reveal max-w-2xl", className)}>
      <p className="text-sm font-medium text-primary">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight text-balance sm:text-5xl sm:leading-[1.08]">
        {title}
      </h2>
      {lead && <p className="mt-4 text-lg text-pretty text-muted-foreground">{lead}</p>}
    </div>
  );
}

/** The small label that marks every mock UI as sample content. */
export function SampleTag({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "rounded-md border px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground",
        className,
      )}
    >
      Sample data
    </span>
  );
}

/** A soft, bordered panel: the base of every mock UI on the page. */
export function Panel({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("rounded-2xl border bg-card text-card-foreground shadow-sm", className)}
      {...props}
    />
  );
}
