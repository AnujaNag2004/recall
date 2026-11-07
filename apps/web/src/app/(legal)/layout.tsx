import Link from "next/link";
import { Footer } from "@/components/landing/footer";
import { Wordmark } from "@/components/landing/primitives";
import { ThemeToggle } from "@/components/theme-toggle";

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between px-4 py-3 sm:px-6">
        <Link href="/" aria-label="Recall home" className="rounded-md">
          <Wordmark className="text-lg" />
        </Link>
        <ThemeToggle />
      </header>
      <main
        id="main"
        className="mx-auto w-full max-w-2xl flex-1 px-4 pt-10 pb-24 sm:px-6 [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-4 [&_h1]:text-3xl [&_h1]:font-semibold [&_h1]:tracking-tight [&_h2]:mt-10 [&_h2]:text-lg [&_h2]:font-semibold [&_li]:mt-2 [&_p]:mt-4 [&_p]:leading-7 [&_p]:text-muted-foreground [&_ul]:mt-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:text-muted-foreground"
      >
        {children}
      </main>
      <Footer />
    </div>
  );
}
