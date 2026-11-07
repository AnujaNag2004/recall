import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/app/page-states";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return <ComingSoonPage href="/settings" />;
}
