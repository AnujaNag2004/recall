import type { Metadata } from "next";
import { Suspense } from "react";
import { AcceptInvite } from "@/components/views/accept-invite";

export const metadata: Metadata = { title: "Invite" };

export default function InvitePage() {
  return (
    <Suspense>
      <AcceptInvite />
    </Suspense>
  );
}
