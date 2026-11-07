import type { Metadata } from "next";
import { ForgotPasswordForm } from "@/components/auth/password-forms";
import { OpeningSoon } from "@/components/opening-soon";
import { isSupabaseConfigured } from "@/lib/supabase/config";

export const metadata: Metadata = { title: "Reset password", robots: { index: false } };

export default function ForgotPasswordPage() {
  if (!isSupabaseConfigured) return <OpeningSoon title="Sign-in opens soon" />;
  return <ForgotPasswordForm />;
}
