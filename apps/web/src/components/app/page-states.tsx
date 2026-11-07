import { CircleAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  lead,
  actions,
}: {
  title: string;
  lead?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {lead && <p className="mt-1 text-sm text-muted-foreground">{lead}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function PageBody({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8", className)}>
      {children}
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-dashed px-6 py-14 text-center">
      <Icon className="mx-auto size-6 text-muted-foreground" aria-hidden />
      <h2 className="mt-4 font-semibold tracking-tight">{title}</h2>
      <p className="mx-auto mt-1.5 max-w-sm text-sm text-pretty text-muted-foreground">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-2xl border border-dashed px-6 py-14 text-center">
      <CircleAlert className="mx-auto size-6 text-muted-foreground" aria-hidden />
      <h2 className="mt-4 font-semibold tracking-tight">That didn&apos;t load</h2>
      <p className="mx-auto mt-1.5 max-w-sm text-sm text-muted-foreground">
        {message ?? "Something went wrong. Please try again."}
      </p>
      {onRetry && (
        <Button variant="outline" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
