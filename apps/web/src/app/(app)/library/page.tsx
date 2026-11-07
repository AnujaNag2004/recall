import type { Metadata } from "next";
import { Suspense } from "react";
import { LibraryView } from "@/components/saves/library-view";

export const metadata: Metadata = { title: "Library" };

export default function LibraryPage() {
  return (
    <Suspense>
      <LibraryView />
    </Suspense>
  );
}
