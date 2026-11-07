import type { Metadata } from "next";
import { AppProviders } from "@/components/app/app-context";
import { AppShell } from "@/components/app/app-shell";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = { robots: { index: false } };

/**
 * The shell is prerendered and fetches user data in the browser, so navigation stays
 * instant. `src/proxy.ts` keeps signed-out visitors from reaching it.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProviders>
      <AppShell>{children}</AppShell>
      <Toaster />
    </AppProviders>
  );
}
