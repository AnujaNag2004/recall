import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/app/page-states";

export const metadata: Metadata = { title: "Inbox" };

export default function InboxPage() {
  return <ComingSoonPage href="/inbox" />;
}
