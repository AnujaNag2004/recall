/** Site-wide facts, so a route or URL only ever changes in one place. */

function resolveSiteUrl(): string {
  if (process.env.NEXT_PUBLIC_SITE_URL) return process.env.NEXT_PUBLIC_SITE_URL;
  // Set automatically on Vercel deployments.
  if (process.env.VERCEL_PROJECT_PRODUCTION_URL) {
    return `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`;
  }
  return "http://localhost:3000";
}

export const site = {
  name: "Recall",
  tagline: "Your AI memory and action layer for everything you save.",
  headline: "Stop saving. Start doing.",
  pitch:
    "Everyone saves hundreds of posts, videos and docs but almost never acts on them. Recall is a multi-agent AI system that turns saved content into context-aware micro-actions, surfaces the right save at the right moment, and tracks whether your saves actually change your behavior.",
  url: resolveSiteUrl(),
  /** Optional: the footer shows a GitHub link only when this is set. */
  githubUrl: process.env.NEXT_PUBLIC_GITHUB_URL,
  routes: {
    signUp: "/signup",
    signIn: "/login",
    demo: "/demo",
  },
} as const;
