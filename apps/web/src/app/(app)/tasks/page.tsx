import type { Metadata } from "next";
import { TasksView } from "@/components/views/tasks-view";

export const metadata: Metadata = { title: "Tasks" };

export default function Page() {
  return <TasksView />;
}
