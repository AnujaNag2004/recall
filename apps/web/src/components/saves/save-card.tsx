import { CircleAlert, FileText, Loader2 } from "lucide-react";
import Link from "next/link";
import type { SaveSummary } from "@/lib/api/client";
import { formatDate, SOURCE_LABELS } from "@/lib/format";

export function SaveCard({ save }: { save: SaveSummary }) {
  const title = save.title || save.source_url || "Untitled save";
  return (
    <Link
      href={`/saves/${save.id}`}
      className="group flex h-full flex-col rounded-xl border bg-card p-4 shadow-sm transition-colors outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <FileText className="size-3.5" aria-hidden />
        <span>{SOURCE_LABELS[save.source_type] ?? save.source_type}</span>
        {save.mode && <span className="capitalize">· {save.mode}</span>}
        <span className="ml-auto">{formatDate(save.created_at)}</span>
      </div>
      <h3 className="mt-2 line-clamp-2 text-sm font-medium tracking-tight break-words">{title}</h3>
      {save.status === "ready" && save.summary && (
        <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-muted-foreground">
          {save.summary}
        </p>
      )}
      {(save.status === "pending" || save.status === "processing") && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Loader2 className="size-3 animate-spin" aria-hidden />
          {save.stage ?? "Waiting to start"}
        </p>
      )}
      {save.status === "failed" && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-destructive">
          <CircleAlert className="size-3" aria-hidden />
          Couldn&apos;t process this
        </p>
      )}
    </Link>
  );
}
