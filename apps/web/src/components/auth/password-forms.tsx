"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { DEFAULT_APP_PATH } from "@/lib/auth-paths";
import { createClient } from "@/lib/supabase/client";
import { AuthHeading, Field, FormError, SubmitButton } from "./fields";

export function ForgotPasswordForm() {
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    const callback = `${window.location.origin}/auth/callback?next=/reset-password`;
    await createClient().auth.resetPasswordForEmail(String(form.get("email")), {
      redirectTo: callback,
    });
    // The same message whatever happened, so this can't reveal which emails exist.
    setPending(false);
    setSent(true);
  };

  if (sent) {
    return (
      <>
        <AuthHeading title="Check your email" />
        <p role="status" className="text-sm text-muted-foreground">
          If that email has an account, a reset link is on its way.
        </p>
        <p className="mt-6 text-sm">
          <Link href="/login" className="font-medium text-primary hover:underline">
            Back to sign in
          </Link>
        </p>
      </>
    );
  }

  return (
    <>
      <AuthHeading title="Reset your password" lead="We'll email you a link to choose a new one." />
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" id="email" type="email" autoComplete="email" />
        <SubmitButton pending={pending}>{pending ? "Sending…" : "Send reset link"}</SubmitButton>
      </form>
      <p className="mt-6 text-sm">
        <Link href="/login" className="text-muted-foreground hover:text-foreground">
          Back to sign in
        </Link>
      </p>
    </>
  );
}

export function ResetPasswordForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    const { error: updateError } = await createClient().auth.updateUser({
      password: String(form.get("password")),
    });
    if (updateError) {
      setPending(false);
      setError(
        updateError.code === "same_password"
          ? "Please choose a password you haven't used here before."
          : "We couldn't update your password. Please request a new link.",
      );
      return;
    }
    router.replace(DEFAULT_APP_PATH);
    router.refresh();
  };

  return (
    <>
      <AuthHeading title="Choose a new password" />
      <form onSubmit={submit} className="space-y-4">
        <Field
          label="New password"
          id="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          hint="At least 8 characters."
        />
        <FormError>{error}</FormError>
        <SubmitButton pending={pending}>{pending ? "Saving…" : "Save password"}</SubmitButton>
      </form>
    </>
  );
}
