import type { Metadata } from "next";
import { OpeningSoon } from "@/components/opening-soon";

export const metadata: Metadata = { title: "Get started", robots: { index: false } };

export default function SignUpPage() {
  return <OpeningSoon title="Sign-ups open soon" />;
}
