import type { Metadata } from "next";
import { AgentRunsView } from "@/components/views/agent-runs";

export const metadata: Metadata = { title: "Agent runs" };

export default function Page() {
  return <AgentRunsView />;
}
