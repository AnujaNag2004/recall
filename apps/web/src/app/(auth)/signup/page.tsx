import type { Metadata } from "next";
import { SignupForm } from "@/components/auth/signup-form";
import { OpeningSoon } from "@/components/opening-soon";
import { isSupabaseConfigured } from "@/lib/supabase/config";

export const metadata: Metadata = { title: "Get started", robots: { index: false } };

export default function SignUpPage() {
  if (!isSupabaseConfigured) return <OpeningSoon title="Sign-ups open soon" />;
  return <SignupForm />;
}
