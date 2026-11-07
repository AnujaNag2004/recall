import { allNav } from "@/lib/nav";

/** The friendly empty state for a page a later phase builds out. */
export function ComingSoonPage({ href }: { href: string }) {
  const item = allNav.find((candidate) => candidate.href === href);
  if (!item) throw new Error(`No nav item for ${href}`);
  return (
    <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center px-4 py-16 text-center">
      <item.icon className="size-6 text-muted-foreground" aria-hidden />
      <h1 className="mt-4 text-xl font-semibold tracking-tight">{item.emptyTitle}</h1>
      <p className="mt-1.5 text-sm text-pretty text-muted-foreground">{item.emptyBody}</p>
    </div>
  );
}
