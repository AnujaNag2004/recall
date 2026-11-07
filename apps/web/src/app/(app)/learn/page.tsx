import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/app/page-states";

export const metadata: Metadata = { title: "Learn" };

export default function LearnPage() {
  return <ComingSoonPage href="/learn" />;
}
