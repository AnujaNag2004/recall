"use server";

import { redirect } from "next/navigation";
import { DEFAULT_APP_PATH, LOGIN_PATH } from "@/lib/auth-paths";
import { getDemoCredentials } from "@/lib/demo";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

export async function signInToDemo() {
  const credentials = getDemoCredentials();
  if (!credentials || !isSupabaseConfigured) redirect(`${LOGIN_PATH}?error=demo`);

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword(credentials);
  redirect(error ? `${LOGIN_PATH}?error=demo` : DEFAULT_APP_PATH);
}
