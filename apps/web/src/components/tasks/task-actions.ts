"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiJson, type Task } from "@/lib/api/client";

/** Everything that changes a task refreshes the views that show tasks and the score. */
function useRefresh() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["tasks", "home", "save", "metrics"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      ),
    );
}

export function useUpdateTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; [field: string]: unknown }) =>
      apiJson<Task>(`/tasks/${id}`, "PATCH", body),
    onSuccess: refresh,
    onError: (error) => toast.error(error.message),
  });
}

export function useRespondToTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({
      id,
      answer,
      reschedule_to,
    }: {
      id: string;
      answer: "done" | "not_yet" | "let_go";
      reschedule_to?: string;
    }) =>
      apiJson<{ task: Task; next_step: Task | null }>(`/tasks/${id}/respond`, "POST", {
        answer,
        reschedule_to,
      }),
    onSuccess: async (result, { answer }) => {
      await refresh();
      if (answer === "done") {
        toast.success(
          result.next_step ? `Nice. Next up: ${result.next_step.title}` : "Nice. That's logged.",
        );
      } else if (answer === "let_go") {
        toast("Let go, no guilt.");
      } else {
        toast("We'll ask again later.");
      }
    },
    onError: (error) => toast.error(error.message),
  });
}
