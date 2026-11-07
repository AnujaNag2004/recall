import type { Metadata } from "next";
import { AuthHeading } from "@/components/auth/fields";
import { DemoButton } from "@/components/auth/demo-button";
import { OpeningSoon } from "@/components/opening-soon";
import { getDemoCredentials } from "@/lib/demo";
import { isSupabaseConfigured } from "@/lib/supabase/config";

export const metadata: Metadata = { title: "Live demo", robots: { index: false } };

export default function DemoPage() {
  if (!isSupabaseConfigured || !getDemoCredentials()) {
    return <OpeningSoon title="The live demo opens soon" />;
  }
  return (
    <>
      <AuthHeading
        title="Try the live demo"
        lead="Look around a shared account, with no sign-up needed. Everyone sees the same data, so please don't save anything private."
      />
      <DemoButton primary />
    </>
  );
}
