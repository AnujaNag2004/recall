import type { Metadata } from "next";
import { GraphView } from "@/components/views/graph-view";

export const metadata: Metadata = { title: "Graph" };

export default function Page() {
  return <GraphView />;
}
