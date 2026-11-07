"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useMe, useWorkspaces } from "./app-context";

export function HomeView() {
  const { data: me, isPending } = useMe();
  const { active } = useWorkspaces();
  const firstName = me?.user.name?.split(" ")[0];

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
      {isPending ? (
        <Skeleton className="h-9 w-56 rounded-lg" />
      ) : (
        <h1 className="text-3xl font-semibold tracking-tight">
          {firstName ? `Welcome, ${firstName}` : "Welcome"}
        </h1>
      )}
      <p className="mt-1.5 text-sm text-muted-foreground">
        {active ? `You're in ${active.name}.` : "Here's where your day starts."}
      </p>

      <div className="mt-8 rounded-2xl border border-dashed px-6 py-14 text-center">
        <Sparkles className="mx-auto size-6 text-primary" aria-hidden />
        <h2 className="mt-4 text-lg font-semibold tracking-tight">Nothing saved yet</h2>
        <p className="mx-auto mt-1.5 max-w-sm text-sm text-pretty text-muted-foreground">
          Your next steps, and the saves that matter right now, will show up here once you start
          saving.
        </p>
        <Link
          href="/inbox"
          className={cn(buttonVariants(), "mt-6 h-10 rounded-lg px-4")}
        >
          Save your first link
        </Link>
      </div>
    </div>
  );
}
