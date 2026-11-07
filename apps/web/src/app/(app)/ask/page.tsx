import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/app/page-states";

export const metadata: Metadata = { title: "Ask" };

export default function AskPage() {
  return <ComingSoonPage href="/ask" />;
}
