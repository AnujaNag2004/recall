import type { Metadata } from "next";
import { InsightsView } from "@/components/views/insights-view";

export const metadata: Metadata = { title: "Insights" };

export default function Page() {
  return <InsightsView />;
}
