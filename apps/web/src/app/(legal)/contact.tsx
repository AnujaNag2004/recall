import { site } from "@/lib/site";

/** Where people can reach the maintainer. Falls back to plain text when no repo is set. */
export function Contact() {
  if (!site.githubUrl) return <>the maintainer of this site</>;
  return (
    <>
      the maintainer, by opening an issue on <a href={`${site.githubUrl}/issues`}>GitHub</a>
    </>
  );
}

export const LAST_UPDATED = "8 November 2026";
