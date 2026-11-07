import Link from "next/link";
import { site } from "@/lib/site";
import { Container, CtaLink, Wordmark } from "./primitives";

export function FinalCta() {
  return (
    <section className="pb-20 sm:pb-28">
      <Container>
        <div className="reveal rounded-3xl border bg-[radial-gradient(60%_90%_at_50%_0%,color-mix(in_oklch,var(--primary)_14%,transparent),transparent)] px-6 py-16 text-center sm:py-24">
          <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
            Do something with what you saved.
          </h2>
          <p className="mx-auto mt-4 max-w-md text-lg text-pretty text-muted-foreground">
            Start with one link. Recall will take it from there.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <CtaLink href={site.routes.signUp}>Get started free</CtaLink>
            <CtaLink href={site.routes.demo} variant="outline">
              Try the live demo
            </CtaLink>
          </div>
        </div>
      </Container>
    </section>
  );
}

export function Footer() {
  const links = [
    // Absolute, so they also work from the legal pages, which share this footer.
    { href: "/#features", label: "Features" },
    { href: "/#how-it-works", label: "How it works" },
    { href: "/#pricing", label: "Pricing" },
    { href: "/#faq", label: "FAQ" },
    { href: "/privacy", label: "Privacy" },
    { href: "/terms", label: "Terms" },
    ...(site.githubUrl ? [{ href: site.githubUrl, label: "GitHub" }] : []),
  ];

  return (
    <footer className="border-t">
      <Container className="flex flex-col gap-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link href="/" aria-label="Recall home" className="rounded-md">
            <Wordmark />
          </Link>
          <p className="mt-2 text-sm text-muted-foreground">Built by Anuja</p>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-md text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>
      </Container>
    </footer>
  );
}
