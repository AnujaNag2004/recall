import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/app/page-states";

export const metadata: Metadata = { title: "Tasks" };

export default function TasksPage() {
  return <ComingSoonPage href="/tasks" />;
}
