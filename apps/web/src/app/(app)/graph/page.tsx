import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/app/page-states";

export const metadata: Metadata = { title: "Graph" };

export default function GraphPage() {
  return <ComingSoonPage href="/graph" />;
}
