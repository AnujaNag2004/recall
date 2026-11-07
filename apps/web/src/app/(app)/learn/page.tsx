import type { Metadata } from "next";
import { LearnView } from "@/components/views/learn-view";

export const metadata: Metadata = { title: "Learn" };

export default function Page() {
  return <LearnView />;
}
