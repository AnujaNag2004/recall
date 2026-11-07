"use client";

import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { DEFAULT_APP_PATH } from "@/lib/auth-paths";
import { createClient } from "@/lib/supabase/client";
import { AuthHeading, Divider, Field, FormError, SubmitButton } from "./fields";
import { GoogleButton } from "./google-button";

const MIN_PASSWORD_LENGTH = 8;

export function SignupForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    setPending(true);
    setError(null);
    const { data, error: signUpError } = await createClient().auth.signUp({
      email,
      password: String(form.get("password")),
      options: {
        data: { full_name: String(form.get("name")) },
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    setPending(false);
    if (signUpError) {
      setError(
        signUpError.code === "weak_password"
          ? "Please choose a stronger password."
          : "We couldn't create your account. Please try again.",
      );
      return;
    }
    if (data.session) {
      // Email confirmation is off for this project, so they're already signed in.
      router.replace(DEFAULT_APP_PATH);
      router.refresh();
      return;
    }
    // Shown for existing emails too: Supabase hides them, and so do we.
    setSentTo(email);
  };

  if (sentTo) {
    return (
      <div className="text-center">
        <MailCheck className="mx-auto size-8 text-primary" aria-hidden />
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">Check your email</h1>
        <p role="status" className="mt-2 text-sm text-muted-foreground">
          If this email is new to us, we&apos;ve sent a confirmation link to{" "}
          <span className="font-medium text-foreground">{sentTo}</span>. Open it to finish signing
          up.
        </p>
      </div>
    );
  }

  return (
    <>
      <AuthHeading title="Create your account" lead="Start turning saves into something you do." />
      <GoogleButton onError={setError} />
      <Divider />
      <form onSubmit={submit} className="space-y-4">
        <Field label="Name" id="name" autoComplete="name" />
        <Field label="Email" id="email" type="email" autoComplete="email" />
        <Field
          label="Password"
          id="password"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        />
        <FormError>{error}</FormError>
        <SubmitButton pending={pending}>
          {pending ? "Creating account…" : "Create account"}
        </SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
