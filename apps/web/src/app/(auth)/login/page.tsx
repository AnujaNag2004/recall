import type { Metadata } from "next";
import { Suspense } from "react";
import { DemoButton } from "@/components/auth/demo-button";
import { LoginForm } from "@/components/auth/login-form";
import { OpeningSoon } from "@/components/opening-soon";
import { getDemoCredentials } from "@/lib/demo";
import { isSupabaseConfigured } from "@/lib/supabase/config";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

export default function LoginPage() {
  if (!isSupabaseConfigured) return <OpeningSoon title="Sign-in opens soon" />;
  return (
    <Suspense>
      <LoginForm demoSlot={getDemoCredentials() ? <DemoButton /> : null} />
    </Suspense>
  );
}
