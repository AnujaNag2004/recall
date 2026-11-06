import Link from "next/link";
import { CtaLink, Wordmark } from "@/components/landing/primitives";

/** Holds the auth and demo routes until Phase 1 replaces them with the real thing. */
export function OpeningSoon({ title }: { title: string }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4 py-24 text-center">
      <Link href="/" aria-label="Recall home" className="rounded-md">
        <Wordmark className="text-lg" />
      </Link>
      <h1 className="mt-8 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{title}</h1>
      <p className="mt-3 max-w-md text-pretty text-muted-foreground">
        Recall is being built in public, and accounts and the live demo aren&apos;t open yet. Check
        back soon.
      </p>
      <CtaLink href="/" variant="outline" className="mt-8">
        Back to the home page
      </CtaLink>
    </main>
  );
}
