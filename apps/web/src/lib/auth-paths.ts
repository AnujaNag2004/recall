/** Where people go after signing in, unless they were heading somewhere specific. */
export const DEFAULT_APP_PATH = "/home";

export const LOGIN_PATH = "/login";

/** Keep in step with the matcher in `src/proxy.ts`; a test checks that they agree. */
export const protectedPrefixes = [
  "/home",
  "/inbox",
  "/ask",
  "/library",
  "/graph",
  "/learn",
  "/tasks",
  "/insights",
  "/settings",
  "/reset-password",
];

/** Pointless once signed in, so signed-in visitors skip straight to the app. */
export const guestOnlyPaths = ["/login", "/signup", "/forgot-password"];

const matchesPrefix = (pathname: string, prefix: string) =>
  pathname === prefix || pathname.startsWith(`${prefix}/`);

export type RouteDecision = { redirect: string } | { redirect: null };

/** The proxy's routing rule, kept pure so it can be tested without a request. */
export function decideRoute(pathname: string, search: string, signedIn: boolean): RouteDecision {
  if (!signedIn && protectedPrefixes.some((prefix) => matchesPrefix(pathname, prefix))) {
    const next = encodeURIComponent(`${pathname}${search}`);
    return { redirect: `${LOGIN_PATH}?next=${next}` };
  }
  if (signedIn && guestOnlyPaths.some((path) => matchesPrefix(pathname, path))) {
    return { redirect: DEFAULT_APP_PATH };
  }
  return { redirect: null };
}

/**
 * Makes a `next` parameter safe to redirect to. It arrives from the URL, so without
 * this a crafted link could bounce someone from our login page to a phishing site.
 */
export function safeNextPath(next: string | null | undefined): string {
  if (!next) return DEFAULT_APP_PATH;
  // "//evil.example" and "/\evil.example" both resolve to another host in browsers.
  if (!next.startsWith("/") || next.startsWith("//") || next.includes("\\")) {
    return DEFAULT_APP_PATH;
  }
  const base = "http://recall.invalid";
  try {
    const url = new URL(next, base);
    return url.origin === base ? `${url.pathname}${url.search}${url.hash}` : DEFAULT_APP_PATH;
  } catch {
    return DEFAULT_APP_PATH;
  }
}
