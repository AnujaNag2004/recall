import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "@/components/theme-provider";
import { ApiError, apiFetch } from "@/lib/api/client";
import { AppProviders } from "./app-context";
import { AppShell } from "./app-shell";
import { HomeView } from "./home-view";

const push = vi.fn();
const signOutMock = vi.fn().mockResolvedValue({});

vi.mock("next/navigation", () => ({
  usePathname: () => "/library",
  useRouter: () => ({ push }),
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signOut: signOutMock } }),
}));
vi.mock("@/lib/api/client", async (original) => ({
  ...(await original<typeof import("@/lib/api/client")>()),
  apiFetch: vi.fn(),
}));

const me = {
  user: {
    id: "u1",
    email: "priya@example.com",
    name: "Priya Sharma",
    avatar_url: null,
    timezone: "UTC",
  },
  workspaces: [
    { id: "w1", name: "Personal", type: "personal", role: "owner" },
    { id: "w2", name: "Startup Squad", type: "team", role: "member" },
  ],
};

function renderShell() {
  return render(
    <ThemeProvider>
      <AppProviders>
        <AppShell>
          <HomeView />
        </AppShell>
      </AppProviders>
    </ThemeProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(apiFetch).mockResolvedValue(me);
});

describe("AppShell", () => {
  it("greets the user and shows their workspace", async () => {
    renderShell();
    expect(await screen.findByRole("heading", { name: "Welcome, Priya" })).toBeInTheDocument();
    expect(screen.getByText("You're in Personal.")).toBeInTheDocument();
    expect(screen.getByText("Nothing saved yet")).toBeInTheDocument();
  });

  it("marks the current page in the sidebar", async () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "App" });
    expect(within(nav).getByRole("link", { name: "Library" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("collapses the sidebar and remembers it, keeping links labelled", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(localStorage.getItem("recall.sidebarCollapsed")).toBe("true");
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tasks" })).toBeInTheDocument();
  });

  it("switches workspace and remembers the choice", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(await screen.findByRole("button", { name: /Switch workspace/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Startup Squad" }));
    expect(await screen.findByText("You're in Startup Squad.")).toBeInTheDocument();
    expect(localStorage.getItem("recall.activeWorkspace")).toBe("w2");
  });

  it("ignores a remembered workspace this user can't access", async () => {
    localStorage.setItem("recall.activeWorkspace", "someone-elses");
    renderShell();
    expect(await screen.findByText("You're in Personal.")).toBeInTheDocument();
  });

  it("offers a retry when the API is down", async () => {
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(500, "boom"));
    renderShell();
    expect(await screen.findByText(/can't reach the server/, {}, { timeout: 9000 })).toBeVisible();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  }, 10000);

  it("signs out when the API rejects the session", async () => {
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(401, "expired"));
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    renderShell();
    await waitFor(() => expect(signOutMock).toHaveBeenCalled());
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/"));
    vi.unstubAllGlobals();
  });
});

describe("command palette", () => {
  it("opens with the keyboard and navigates", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.keyboard("{Meta>}k{/Meta}");
    const input = await screen.findByPlaceholderText("Type a command or page…");
    await user.type(input, "insights");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/insights"));
  });

  it("opens from the search button", async () => {
    const user = userEvent.setup();
    renderShell();
    await user.click(screen.getByRole("button", { name: /Search or jump to/ }));
    expect(await screen.findByPlaceholderText("Type a command or page…")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Quick save" })).toBeInTheDocument();
  });
});
