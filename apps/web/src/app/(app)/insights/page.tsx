import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/app/page-states";

export const metadata: Metadata = { title: "Insights" };

export default function InsightsPage() {
  return <ComingSoonPage href="/insights" />;
}
