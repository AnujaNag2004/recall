import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CaptureForm } from "@/components/saves/capture-form";
import { SmartCard } from "@/components/saves/smart-card";
import { ChatThread } from "@/components/ask/chat-thread";
import { apiFetch, apiJson, type SaveDetail } from "@/lib/api/client";
import { HomeView } from "./home-view";
import { LearnView } from "./learn-view";
import { TasksView } from "./tasks-view";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  useParams: () => ({ id: "s1" }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/app/app-context", () => ({
  useMe: () => ({ data: { user: { name: "Priya Sharma" } } }),
  useWorkspaces: () => ({ active: { id: "w1", name: "Personal", role: "owner" }, workspaces: [] }),
  signOut: vi.fn(),
}));
vi.mock("@/lib/api/client", async (original) => ({
  ...(await original<typeof import("@/lib/api/client")>()),
  apiFetch: vi.fn(),
  apiJson: vi.fn(),
  streamEvents: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const task = (over: object = {}) => ({
  id: "t1",
  workspace_id: "w1",
  save_id: "s1",
  save_title: "Graphs",
  title: "Solve one problem",
  description: null,
  type: "micro_action",
  assignee_id: null,
  due_at: null,
  scheduled_for: null,
  status: "accepted",
  size: "tiny",
  followup_at: null,
  completed_at: null,
  source_agent: null,
  skip_count: 0,
  created_at: "2026-11-01T00:00:00Z",
  ...over,
});

const card = (over: Partial<SaveDetail> = {}) => ({
  id: "s1",
  workspace_id: "w1",
  title: "Graph algorithms",
  source_url: "https://youtu.be/abcdefghijk",
  source_type: "youtube",
  thumbnail_url: null,
  mode: "study",
  status: "ready",
  stage: null,
  error: null,
  summary: "A tour of graphs.",
  intent: "learn",
  created_at: "2026-11-01T00:00:00Z",
  author: null,
  key_points: ["BFS finds shortest paths."],
  content_template: "study",
  language: "en",
  raw_text: null,
  embed_youtube_id: "abcdefghijk",
  file_url: null,
  file_type: null,
  transcript: [{ start: 65, end: 70, text: "Now the second part." }],
  resources: [
    {
      id: "r1",
      name: "VisuAlgo",
      entity_type: "website",
      mention_ts: 12,
      url: "https://visualgo.net",
      domain: "visualgo.net",
      title: null,
      description: "Visual algorithms",
      favicon_url: null,
      pricing: "free",
      category: "website",
      confidence: 0.92,
      verified: true,
    },
    {
      id: "r2",
      name: "Mystery tool",
      entity_type: "tool",
      mention_ts: null,
      url: null,
      domain: null,
      title: null,
      description: null,
      favicon_url: null,
      pricing: null,
      category: null,
      confidence: null,
      verified: false,
    },
  ],
  tasks: [task({ status: "suggested" })],
  topics: [{ id: "tp1", name: "Algorithms" }],
  related: [],
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CaptureForm", () => {
  it("treats a single token with a dot as a link, and sends the intent", async () => {
    vi.mocked(apiJson).mockResolvedValue({ id: "new" });
    const user = userEvent.setup();
    wrap(<CaptureForm />);
    await user.type(screen.getByLabelText(/Paste a link/), "youtu.be/abc123");
    await user.click(screen.getByRole("button", { name: "learn" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/saves/new"));
    expect(apiJson).toHaveBeenCalledWith("/workspaces/w1/saves", "POST", {
      url: "youtu.be/abc123",
      intent: "learn",
    });
  });

  it("treats sentences as notes", async () => {
    vi.mocked(apiJson).mockResolvedValue({ id: "new" });
    const user = userEvent.setup();
    wrap(<CaptureForm />);
    await user.type(screen.getByLabelText(/Paste a link/), "Call the dentist. Soon.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(apiJson).toHaveBeenCalledWith("/workspaces/w1/saves", "POST", {
        text: "Call the dentist. Soon.",
        intent: null,
      }),
    );
  });
});

describe("SmartCard", () => {
  it("embeds YouTube from the verified id, with privacy mode and a sandbox", async () => {
    vi.mocked(apiFetch).mockResolvedValue(card());
    wrap(<SmartCard />);
    const frame = await screen.findByTitle("Graph algorithms");
    expect(frame.getAttribute("src")).toContain("youtube-nocookie.com/embed/abcdefghijk");
    expect(frame.getAttribute("sandbox")).toBeTruthy();
  });

  it("clicking a transcript line seeks the video", async () => {
    vi.mocked(apiFetch).mockResolvedValue(card());
    const user = userEvent.setup();
    wrap(<SmartCard />);
    await user.click(await screen.findByRole("button", { name: /Now the second part/ }));
    expect(screen.getByTitle("Graph algorithms").getAttribute("src")).toContain("start=65");
  });

  it("labels verified links, and never links an unverified name", async () => {
    vi.mocked(apiFetch).mockResolvedValue(card());
    const user = userEvent.setup();
    wrap(<SmartCard />);
    await user.click(await screen.findByRole("tab", { name: "Resources" }));
    expect(screen.getByText(/Verified · visualgo.net/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /VisuAlgo/ })).toHaveAttribute(
      "rel",
      "noopener noreferrer nofollow",
    );
    expect(screen.getByText("No official link found")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Mystery tool/ })).not.toBeInTheDocument();
  });

  it("requires approval before a suggested task joins Tasks", async () => {
    vi.mocked(apiFetch).mockResolvedValue(card());
    vi.mocked(apiJson).mockResolvedValue(task());
    const user = userEvent.setup();
    wrap(<SmartCard />);
    await user.click(await screen.findByRole("tab", { name: "Actions" }));
    expect(apiJson).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Add to tasks" }));
    await waitFor(() =>
      expect(apiJson).toHaveBeenCalledWith("/tasks/t1", "PATCH", { status: "accepted" }),
    );
  });

  it("explains a failure and offers a retry", async () => {
    vi.mocked(apiFetch).mockResolvedValue(card({ status: "failed", error: "No transcript." }));
    wrap(<SmartCard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No transcript.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows the live stage while processing", async () => {
    vi.mocked(apiFetch).mockResolvedValue(
      card({ status: "processing", stage: "Writing the summary", summary: null }),
    );
    wrap(<SmartCard />);
    expect(await screen.findByRole("status")).toHaveTextContent("Writing the summary");
  });
});

const home = (over: object = {}) => ({
  recall_cards: [],
  followups: [],
  today: [],
  suggested: [],
  review_count: 2,
  score: { acted: 1, total: 4, ratio: 0.25 },
  streak_days: 3,
  recent_saves: [card()],
  ...over,
});

describe("HomeView", () => {
  it("runs the follow-up loop from Home", async () => {
    vi.mocked(apiFetch).mockResolvedValue(home({ followups: [task()] }));
    vi.mocked(apiJson).mockResolvedValue({ task: task({ status: "done" }), next_step: null });
    const user = userEvent.setup();
    wrap(<HomeView />);
    expect(await screen.findByText("Did you do it?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Done" }));
    await waitFor(() =>
      expect(apiJson).toHaveBeenCalledWith("/tasks/t1/respond", "POST", { answer: "done" }),
    );
  });

  it("asks keep or let go after two skips", async () => {
    vi.mocked(apiFetch).mockResolvedValue(home({ followups: [task({ skip_count: 2 })] }));
    wrap(<HomeView />);
    expect(await screen.findByText(/Keep it, or let it go/)).toBeInTheDocument();
  });

  it("shows the score, streak and review count", async () => {
    vi.mocked(apiFetch).mockResolvedValue(home());
    wrap(<HomeView />);
    expect(await screen.findByText("25%")).toBeInTheDocument();
    expect(screen.getByText("3 day streak")).toBeInTheDocument();
    expect(screen.getByText("2 cards to review")).toBeInTheDocument();
  });
});

describe("TasksView", () => {
  it("sorts tasks into Today, Upcoming and Done", async () => {
    const later = new Date(Date.now() + 5 * 86400000).toISOString();
    vi.mocked(apiFetch).mockImplementation(async (path: string) =>
      path.includes("google")
        ? { configured: false, connected: false }
        : [
            task({ id: "a", title: "Now" }),
            task({ id: "b", title: "Later", scheduled_for: later }),
            task({ id: "c", title: "Finished", status: "done" }),
          ],
    );
    wrap(<TasksView />);
    expect((await screen.findByRole("region", { name: "Today" })).textContent).toContain("Now");
    expect(screen.getByRole("region", { name: "Upcoming" }).textContent).toContain("Later");
    expect(screen.getByRole("region", { name: "Done" }).textContent).toContain("Finished");
  });
});

describe("LearnView", () => {
  it("flips a card, then grades it", async () => {
    vi.mocked(apiFetch).mockResolvedValue([
      {
        id: "f1",
        save_id: null,
        front: "What is BFS?",
        back: "A search.",
        due_at: "",
        interval_days: 0,
        repetitions: 0,
      },
    ]);
    vi.mocked(apiJson).mockResolvedValue({});
    const user = userEvent.setup();
    wrap(<LearnView />);
    expect(await screen.findByText("What is BFS?")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Good" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show answer" }));
    await user.click(screen.getByRole("button", { name: "Good" }));
    await waitFor(() =>
      expect(apiJson).toHaveBeenCalledWith("/flashcards/f1/review", "POST", { grade: 4 }),
    );
  });
});

describe("ChatThread", () => {
  it("turns citation markers into chips and never renders the answer as HTML", async () => {
    const onOpen = userEvent.setup();
    wrap(
      <ChatThread
        busy={false}
        onSend={vi.fn()}
        placeholder="Ask"
        messages={[
          {
            id: "1",
            role: "assistant",
            content: "BFS is best [1]. <img src=x onerror=alert(1)>",
            sources: [
              {
                number: 1,
                kind: "save",
                title: "Graphs",
                snippet: "Passage",
                save_id: "s1",
                start_ts: null,
                url: null,
              },
            ],
            citations: [],
            grounded: true,
          },
        ]}
      />,
    );
    expect(document.querySelector("img")).toBeNull();
    await onOpen.click(screen.getByRole("button", { name: "Source 1: Graphs" }));
    expect(screen.getByText("Passage")).toBeInTheDocument();
  });

  it("warns when an answer couldn't be fully supported", () => {
    wrap(
      <ChatThread
        busy={false}
        onSend={vi.fn()}
        placeholder="Ask"
        messages={[{ id: "1", role: "assistant", content: "Maybe.", grounded: false }]}
      />,
    );
    expect(screen.getByText(/may go beyond your sources/)).toBeInTheDocument();
  });
});
