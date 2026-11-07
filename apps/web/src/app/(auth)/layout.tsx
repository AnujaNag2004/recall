import Link from "next/link";
import { Wordmark } from "@/components/landing/primitives";
import { ThemeToggle } from "@/components/theme-toggle";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between px-4 py-3 sm:px-6">
        <Link href="/" aria-label="Recall home" className="rounded-md">
          <Wordmark className="text-lg" />
        </Link>
        <ThemeToggle />
      </header>
      <main className="flex flex-1 flex-col items-center justify-center px-4 pt-8 pb-24">
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}
