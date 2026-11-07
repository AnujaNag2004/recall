import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/app/page-states";

export const metadata: Metadata = { title: "Library" };

export default function LibraryPage() {
  return <ComingSoonPage href="/library" />;
}
