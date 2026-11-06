import type { Metadata } from "next";
import { OpeningSoon } from "@/components/opening-soon";

export const metadata: Metadata = { title: "Live demo", robots: { index: false } };

export default function DemoPage() {
  return <OpeningSoon title="The live demo opens soon" />;
}
