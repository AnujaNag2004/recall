import type { Metadata } from "next";
import { OpeningSoon } from "@/components/opening-soon";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

export default function LoginPage() {
  return <OpeningSoon title="Sign-in opens soon" />;
}
