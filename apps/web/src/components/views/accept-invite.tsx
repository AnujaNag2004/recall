"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { PageBody } from "@/components/app/page-states";
import { useWorkspaces } from "@/components/app/app-context";
import { Button } from "@/components/ui/button";
import { apiJson } from "@/lib/api/client";

export function AcceptInvite() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { setActive } = useWorkspaces();
  const accept = useMutation({
    mutationFn: () => apiJson<{ id: string; name: string }>(`/invites/${token}/accept`, "POST"),
    onSuccess: async (workspace) => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      setActive(workspace.id);
      router.replace("/home");
    },
  });
  return (
    <PageBody className="max-w-md text-center">
      <h1 className="mt-16 text-2xl font-semibold tracking-tight">You&apos;ve been invited</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Join this team workspace to share saves and tasks with them.
      </p>
      {accept.isError && (
        <p role="alert" className="mt-4 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {accept.error.message}
        </p>
      )}
      <Button className="mt-6 h-10 px-6" disabled={accept.isPending} onClick={() => accept.mutate()}>
        {accept.isPending ? "Joining…" : "Accept invite"}
      </Button>
    </PageBody>
  );
}
