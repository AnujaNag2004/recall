import type { Metadata } from "next";
import { ResetPasswordForm } from "@/components/auth/password-forms";

export const metadata: Metadata = { title: "New password", robots: { index: false } };

/** Only reachable with the session from a reset link; the proxy guards it. */
export default function ResetPasswordPage() {
  return <ResetPasswordForm />;
}
