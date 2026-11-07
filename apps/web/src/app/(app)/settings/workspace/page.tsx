import type { Metadata } from "next";
import { WorkspaceSettings } from "@/components/views/workspace-settings";

export const metadata: Metadata = { title: "Workspace" };

export default function Page() {
  return <WorkspaceSettings />;
}
