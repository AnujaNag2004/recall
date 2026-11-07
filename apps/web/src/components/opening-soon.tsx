import { CtaLink } from "@/components/landing/primitives";

/** Shown by the auth and demo routes until Supabase (or the demo login) is configured. */
export function OpeningSoon({ title }: { title: string }) {
  return (
    <div className="text-center">
      <h1 className="text-3xl font-semibold tracking-tight text-balance">{title}</h1>
      <p className="mt-3 max-w-md text-pretty text-muted-foreground">
        This isn&apos;t switched on for this site yet. Check back soon.
      </p>
      <CtaLink href="/" variant="outline" className="mt-8">
        Back to the home page
      </CtaLink>
    </div>
  );
}
