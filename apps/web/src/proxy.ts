import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";
import { decideRoute } from "@/lib/auth-paths";
import { isSupabaseConfigured, supabasePublishableKey, supabaseUrl } from "@/lib/supabase/config";

/**
 * Refreshes the session cookie and guards app routes. It's a convenience layer for
 * the UI: real authorization happens in the API and in row-level security.
 */
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  const redirectIfNeeded = (signedIn: boolean, response: NextResponse) => {
    const { redirect } = decideRoute(pathname, search, signedIn);
    if (!redirect) return response;
    const redirectResponse = NextResponse.redirect(new URL(redirect, request.url));
    // Carry over any refreshed tokens, or the browser and server fall out of sync.
    for (const cookie of response.cookies.getAll()) redirectResponse.cookies.set(cookie);
    return redirectResponse;
  };

  if (!isSupabaseConfigured) return redirectIfNeeded(false, NextResponse.next());

  let response = NextResponse.next({ request });
  const supabase = createServerClient(supabaseUrl, supabasePublishableKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (cookiesToSet, headers) => {
        for (const { name, value } of cookiesToSet) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
        // Stops a CDN caching a response that sets one person's session cookie.
        for (const [key, value] of Object.entries(headers)) response.headers.set(key, value);
      },
    },
  });

  // Keep this call right here: it's what refreshes an expiring session.
  const { data } = await supabase.auth.getClaims();
  return redirectIfNeeded(Boolean(data?.claims), response);
}

export const config = {
  // Explicit, so the marketing pages and static files never pay for a session check.
  matcher: [
    "/home/:path*",
    "/inbox/:path*",
    "/ask/:path*",
    "/library/:path*",
    "/graph/:path*",
    "/learn/:path*",
    "/tasks/:path*",
    "/insights/:path*",
    "/settings/:path*",
    "/reset-password",
    "/login",
    "/signup",
    "/forgot-password",
  ],
};
