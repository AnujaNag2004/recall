import "server-only";

/** The shared demo login. Server-only: the password never reaches the browser. */
export function getDemoCredentials() {
  const email = process.env.DEMO_EMAIL;
  const password = process.env.DEMO_PASSWORD;
  return email && password ? { email, password } : null;
}
