"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Link2, Loader2, UploadCloud } from "lucide-react";
import { useRouter } from "next/navigation";
import { type DragEvent, type FormEvent, useRef, useState } from "react";
import { toast } from "sonner";
import { useWorkspaces } from "@/components/app/app-context";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch, apiJson, type SaveSummary } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export const INTENTS = ["learn", "try", "buy", "cook", "do at work", "reference", "just vibes"];
const MAX_MB = 25;
const ACCEPT =
  "application/pdf,image/png,image/jpeg,image/webp,audio/mpeg,audio/mp4,audio/x-m4a,audio/wav,audio/webm,audio/ogg,video/mp4,video/webm,video/quicktime";

export function CaptureForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { active } = useWorkspaces();
  const fileInput = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const [intent, setIntent] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const finish = async (save: SaveSummary) => {
    await queryClient.invalidateQueries({ queryKey: ["saves"] });
    router.push(`/saves/${save.id}`);
  };

  const fail = (caught: unknown) => {
    setPending(false);
    setError(caught instanceof ApiError ? caught.message : "That didn't save. Please try again.");
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const content = value.trim();
    if (!active || !content) return;
    setPending(true);
    setError(null);
    // One box for both: a single token that looks like a link is treated as one.
    const isLink = /^(https?:\/\/)?[^\s/]+\.[^\s]{2,}$/i.test(content);
    try {
      await finish(
        await apiJson<SaveSummary>(`/workspaces/${active.id}/saves`, "POST", {
          ...(isLink ? { url: content } : { text: content }),
          intent,
        }),
      );
    } catch (caught) {
      fail(caught);
    }
  };

  const upload = async (file: File | undefined) => {
    if (!active || !file) return;
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`Files can be up to ${MAX_MB} MB.`);
      return;
    }
    setPending(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const save = await apiFetch<SaveSummary>(`/workspaces/${active.id}/saves/upload`, {
        method: "POST",
        body: form,
      });
      if (intent) await apiJson(`/saves/${save.id}`, "PATCH", { intent });
      toast.success("Uploaded. Recall is reading it now.");
      await finish(save);
    } catch (caught) {
      fail(caught);
    }
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    void upload(event.dataTransfer.files[0]);
  };

  return (
    <form
      onSubmit={submit}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        "rounded-2xl border bg-card p-4 shadow-sm transition-colors sm:p-5",
        dragging && "border-primary bg-primary/5",
      )}
    >
      <label htmlFor="capture" className="flex items-center gap-2 text-sm font-medium">
        <Link2 className="size-4 text-muted-foreground" aria-hidden />
        Paste a link, or type a note
      </label>
      <textarea
        id="capture"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) void submit(event);
        }}
        rows={3}
        placeholder="https://youtu.be/… or anything you want to remember"
        className="mt-2 w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />

      <fieldset className="mt-3">
        <legend className="text-sm text-muted-foreground">
          Why&apos;d you save this? <span className="text-xs">Optional</span>
        </legend>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {INTENTS.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={intent === option}
              onClick={() => setIntent(intent === option ? null : option)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
                intent === option
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {option}
            </button>
          ))}
        </div>
      </fieldset>

      {error && (
        <p role="alert" className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <Button
          type="button"
          variant="outline"
          className="h-10 rounded-lg"
          disabled={pending}
          onClick={() => fileInput.current?.click()}
        >
          <UploadCloud aria-hidden />
          Upload a file
        </Button>
        <input
          ref={fileInput}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          tabIndex={-1}
          aria-label="Choose a file to upload"
          onChange={(event) => void upload(event.target.files?.[0])}
        />
        <Button type="submit" className="h-10 rounded-lg px-5" disabled={pending || !value.trim()}>
          {pending && <Loader2 className="animate-spin" aria-hidden />}
          {pending ? "Saving…" : "Save"}
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Or drop a PDF, image, audio or video file here, up to {MAX_MB} MB.
      </p>
    </form>
  );
}
