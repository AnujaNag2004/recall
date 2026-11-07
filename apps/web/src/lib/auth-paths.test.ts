import { describe, expect, it } from "vitest";
import { config } from "@/proxy";
import { allNav } from "./nav";
import { decideRoute, guestOnlyPaths, protectedPrefixes, safeNextPath } from "./auth-paths";

describe("safeNextPath", () => {
  it.each([
    ["/library", "/library"],
    ["/library?mode=study#top", "/library?mode=study#top"],
    [null, "/home"],
    ["", "/home"],
  ])("keeps %s as %s", (input, expected) => {
    expect(safeNextPath(input)).toBe(expected);
  });

  it.each([
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "\\\\evil.example",
    "javascript:alert(1)",
    "evil.example",
    "/%5Cevil.example\\",
  ])("refuses the open redirect %s", (input) => {
    expect(safeNextPath(input)).toBe("/home");
  });
});

describe("decideRoute", () => {
  it("sends signed-out visitors to sign in, remembering where they were going", () => {
    expect(decideRoute("/library", "?mode=study", false).redirect).toBe(
      "/login?next=%2Flibrary%3Fmode%3Dstudy",
    );
  });

  it("protects nested routes too", () => {
    expect(decideRoute("/library/abc", "", false).redirect).toContain("/login");
  });

  it("does not confuse a similar path with a protected one", () => {
    expect(decideRoute("/homepage", "", false).redirect).toBeNull();
  });

  it("lets signed-out visitors reach the auth pages", () => {
    expect(decideRoute("/login", "", false).redirect).toBeNull();
  });

  it("skips the auth pages once signed in", () => {
    expect(decideRoute("/signup", "", true).redirect).toBe("/home");
  });

  it("leaves the password reset page reachable when signed in", () => {
    expect(decideRoute("/reset-password", "", true).redirect).toBeNull();
  });
});

describe("route lists", () => {
  it("protects every page in the navigation", () => {
    for (const item of allNav) expect(protectedPrefixes).toContain(item.href);
  });

  it("runs the proxy on every protected and guest-only path", () => {
    // A missing matcher entry would silently leave a page unguarded.
    const matched = config.matcher.map((entry) => entry.replace("/:path*", ""));
    for (const path of [...protectedPrefixes, ...guestOnlyPaths]) expect(matched).toContain(path);
  });
});
