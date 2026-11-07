"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { useWorkspaces } from "@/components/app/app-context";
import { EmptyState, ErrorState, PageBody, PageHeader } from "@/components/app/page-states";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  apiFetch,
  apiJson,
  type Flashcard,
  type Quiz,
  type SaveList,
} from "@/lib/api/client";
import { cn } from "@/lib/utils";

const GRADES = [
  { label: "Forgot", grade: 1, variant: "outline" },
  { label: "Hard", grade: 3, variant: "outline" },
  { label: "Good", grade: 4, variant: "secondary" },
  { label: "Easy", grade: 5, variant: "default" },
] as const;

function Review({ cards }: { cards: Flashcard[] }) {
  const queryClient = useQueryClient();
  const [flipped, setFlipped] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const card = cards[0];

  const review = useMutation({
    mutationFn: (grade: number) => apiJson(`/flashcards/${card.id}/review`, "POST", { grade }),
    onSuccess: async () => {
      setFlipped(false);
      setExplanation(null);
      await queryClient.invalidateQueries({ queryKey: ["learn"] });
      await queryClient.invalidateQueries({ queryKey: ["home"] });
    },
    onError: (error) => toast.error(error.message),
  });
  const explain = useMutation({
    mutationFn: (direction: "simpler" | "deeper") =>
      apiJson<{ text: string }>(`/flashcards/${card.id}/explain`, "POST", { direction }),
    onSuccess: (result) => setExplanation(result.text),
    onError: (error) => toast.error(error.message),
  });

  return (
    <div className="mx-auto max-w-xl">
      <p className="mb-3 text-center text-xs text-muted-foreground tabular-nums">
        {cards.length} to review
      </p>
      <button
        type="button"
        onClick={() => setFlipped(!flipped)}
        aria-label={flipped ? "Show the question" : "Show the answer"}
        className="block w-full rounded-2xl outline-none [perspective:1200px] focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span
          className={cn(
            "relative block min-h-56 transition-transform duration-500 [transform-style:preserve-3d] motion-reduce:transition-none",
            flipped && "[transform:rotateY(180deg)]",
          )}
        >
          <span className="absolute inset-0 flex items-center justify-center rounded-2xl border bg-card p-6 text-lg font-medium shadow-sm [backface-visibility:hidden]">
            {card.front}
          </span>
          <span className="absolute inset-0 flex items-center justify-center rounded-2xl border bg-card p-6 text-base shadow-sm [backface-visibility:hidden] [transform:rotateY(180deg)]">
            {card.back}
          </span>
        </span>
      </button>
      {card.save_id && card.save_title && (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          From{" "}
          <Link href={`/saves/${card.save_id}`} className="hover:underline">
            {card.save_title}
          </Link>
        </p>
      )}
      {flipped ? (
        <>
          <div className="mt-4 grid grid-cols-4 gap-2">
            {GRADES.map(({ label, grade, variant }) => (
              <Button
                key={label}
                variant={variant}
                className="h-10"
                disabled={review.isPending}
                onClick={() => review.mutate(grade)}
              >
                {label}
              </Button>
            ))}
          </div>
          <div className="mt-3 flex justify-center gap-2">
            <Button size="sm" variant="ghost" disabled={explain.isPending} onClick={() => explain.mutate("simpler")}>
              Explain simpler
            </Button>
            <Button size="sm" variant="ghost" disabled={explain.isPending} onClick={() => explain.mutate("deeper")}>
              Go deeper
            </Button>
          </div>
          {explain.isPending && <Skeleton className="mt-3 h-20 rounded-xl" />}
          {explanation && (
            <p className="mt-3 rounded-xl border p-4 text-sm leading-relaxed whitespace-pre-wrap">
              {explanation}
            </p>
          )}
        </>
      ) : (
        <Button className="mt-4 h-10 w-full" onClick={() => setFlipped(true)}>
          Show answer
        </Button>
      )}
    </div>
  );
}

function QuizPanel({ workspaceId }: { workspaceId: string }) {
  const [saveId, setSaveId] = useState("");
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const saves = useQuery({
    queryKey: ["saves", workspaceId, "ready"],
    queryFn: () => apiFetch<SaveList>(`/workspaces/${workspaceId}/saves?status=ready&limit=100`),
  });
  const quiz = useMutation({
    mutationFn: () => apiJson<Quiz>(`/saves/${saveId}/quiz`, "POST"),
    onSuccess: () => setAnswers({}),
    onError: (error) => toast.error(error.message),
  });
  const questions = quiz.data?.questions ?? [];
  const finished = questions.length > 0 && Object.keys(answers).length === questions.length;
  const score = questions.filter((q, i) => answers[i] === q.answer_index).length;

  return (
    <div className="mx-auto max-w-xl">
      <div className="flex gap-2">
        <select
          aria-label="Choose a save to be quizzed on"
          value={saveId}
          onChange={(event) => setSaveId(event.target.value)}
          className="h-10 min-w-0 flex-1 rounded-lg border bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">Choose a save</option>
          {saves.data?.items.map((save) => (
            <option key={save.id} value={save.id}>
              {save.title ?? "Untitled save"}
            </option>
          ))}
        </select>
        <Button className="h-10" disabled={!saveId || quiz.isPending} onClick={() => quiz.mutate()}>
          {quiz.isPending ? "Writing…" : "Quiz me"}
        </Button>
      </div>
      <ol className="mt-6 space-y-6">
        {questions.map((question, index) => (
          <li key={index}>
            <p className="font-medium">
              {index + 1}. {question.question}
            </p>
            <div className="mt-2 grid gap-1.5">
              {question.options.map((option, optionIndex) => {
                const chosen = answers[index] === optionIndex;
                const answered = answers[index] !== undefined;
                const correct = optionIndex === question.answer_index;
                return (
                  <button
                    key={optionIndex}
                    type="button"
                    disabled={answered}
                    onClick={() => setAnswers({ ...answers, [index]: optionIndex })}
                    className={cn(
                      "rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                      !answered && "hover:bg-muted",
                      answered && correct && "border-primary bg-primary/10 font-medium",
                      answered && chosen && !correct && "border-destructive bg-destructive/10",
                    )}
                  >
                    {option}
                    {answered && correct && <span className="sr-only"> (correct answer)</span>}
                    {answered && chosen && !correct && <span className="sr-only"> (your answer, incorrect)</span>}
                  </button>
                );
              })}
            </div>
          </li>
        ))}
      </ol>
      {finished && (
        <p role="status" className="mt-6 rounded-xl border p-4 text-center font-medium">
          You got {score} of {questions.length}.
        </p>
      )}
    </div>
  );
}

export function LearnView() {
  const { active } = useWorkspaces();
  const queue = useQuery({
    queryKey: ["learn", active?.id],
    queryFn: () => apiFetch<Flashcard[]>(`/workspaces/${active?.id}/learn/queue`),
    enabled: Boolean(active),
  });

  return (
    <PageBody>
      <PageHeader title="Learn" lead="Spaced repetition, so what you save actually sticks." />
      <Tabs defaultValue="review" className="mt-6 gap-6">
        <TabsList className="group-data-horizontal/tabs:h-10">
          <TabsTrigger value="review" className="px-4">Review</TabsTrigger>
          <TabsTrigger value="quiz" className="px-4">Quiz</TabsTrigger>
        </TabsList>
        <TabsContent value="review">
          {queue.isPending ? (
            <Skeleton className="mx-auto h-56 max-w-xl rounded-2xl" />
          ) : queue.isError ? (
            <ErrorState message={queue.error.message} onRetry={() => void queue.refetch()} />
          ) : queue.data.length === 0 ? (
            <EmptyState
              icon={GraduationCap}
              title="Nothing due right now"
              body="Open any save and choose Make flashcards. Reviews get scheduled for you."
              action={
                <Link href="/library" className={buttonVariants({ variant: "outline" })}>
                  Go to Library
                </Link>
              }
            />
          ) : (
            <Review cards={queue.data} />
          )}
        </TabsContent>
        <TabsContent value="quiz">{active && <QuizPanel workspaceId={active.id} />}</TabsContent>
      </Tabs>
    </PageBody>
  );
}
