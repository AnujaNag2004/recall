import { ThemeToggle } from "@/components/theme-toggle";

/** Temporary home page. Phase 0.5 replaces it with the full landing page. */
export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between px-6 py-4">
        <span className="text-lg font-semibold tracking-tight">Recall</span>
        <ThemeToggle />
      </header>
      <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6 pb-24 text-center">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Stop saving. <span className="text-primary">Start doing.</span>
        </h1>
        <p className="max-w-md text-muted-foreground">
          Your AI memory and action layer for everything you save.
        </p>
      </main>
    </div>
  );
}
