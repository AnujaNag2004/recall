import { type NextRequest, NextResponse } from "next/server";
import { LOGIN_PATH, safeNextPath } from "@/lib/auth-paths";
import { createClient } from "@/lib/supabase/server";

/** Where Google sign-in, email confirmation and password-reset links land. */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${safeNextPath(searchParams.get("next"))}`);
    }
  }
  return NextResponse.redirect(`${origin}${LOGIN_PATH}?error=link`);
}
