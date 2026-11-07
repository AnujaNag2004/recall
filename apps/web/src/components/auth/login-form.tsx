"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";
import { safeNextPath } from "@/lib/auth-paths";
import { createClient } from "@/lib/supabase/client";
import { AuthHeading, Divider, Field, FormError, SubmitButton } from "./fields";
import { GoogleButton } from "./google-button";

const linkErrors: Record<string, string> = {
  link: "That link has expired or was already used. Please try again.",
  demo: "The demo account isn't available right now.",
};

export function LoginForm({ demoSlot }: { demoSlot?: React.ReactNode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next");
  const [error, setError] = useState<string | null>(
    linkErrors[searchParams.get("error") ?? ""] ?? null,
  );
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    const { error: signInError } = await createClient().auth.signInWithPassword({
      email: String(form.get("email")),
      password: String(form.get("password")),
    });
    if (signInError) {
      setPending(false);
      // The same wording for every failure, so this form can't reveal which emails exist.
      setError(
        signInError.code === "email_not_confirmed"
          ? "Please confirm your email first. Check your inbox for the link."
          : "That email and password don't match.",
      );
      return;
    }
    router.replace(safeNextPath(next));
    router.refresh();
  };

  return (
    <>
      <AuthHeading title="Welcome back" lead="Sign in to get back to what you saved." />
      <GoogleButton next={next} onError={setError} />
      <Divider />
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" id="email" type="email" autoComplete="email" />
        <Field label="Password" id="password" type="password" autoComplete="current-password" />
        <FormError>{error}</FormError>
        <SubmitButton pending={pending}>{pending ? "Signing in…" : "Sign in"}</SubmitButton>
      </form>
      {demoSlot}
      <div className="mt-6 flex justify-between text-sm">
        <Link href="/forgot-password" className="text-muted-foreground hover:text-foreground">
          Forgot password?
        </Link>
        <Link href="/signup" className="font-medium text-primary hover:underline">
          Create account
        </Link>
      </div>
    </>
  );
}
