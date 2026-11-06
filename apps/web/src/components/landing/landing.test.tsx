import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { site } from "@/lib/site";
import { Faq } from "./faq";
import { Hero } from "./hero";
import { MotionProvider } from "./motion-provider";
import { Navbar } from "./navbar";
import { Pricing } from "./pricing";
import { SaveToAction } from "./save-to-action";
import { SmartCardShowcase } from "./smart-card-showcase";
import { UseCases } from "./use-cases";

const renderInMotion = (ui: ReactNode) => render(<MotionProvider>{ui}</MotionProvider>);

describe("calls to action", () => {
  it("hero buttons go to sign-up and the demo", () => {
    renderInMotion(<Hero />);
    expect(screen.getByRole("link", { name: "Get started free" })).toHaveAttribute(
      "href",
      site.routes.signUp,
    );
    expect(screen.getByRole("link", { name: "Try the live demo" })).toHaveAttribute(
      "href",
      site.routes.demo,
    );
  });

  it("pricing says it is a mock and every plan links to sign-up", () => {
    render(<Pricing />);
    expect(screen.getByText(/mock pricing table/i)).toBeInTheDocument();
    for (const plan of ["Free", "Pro", "Team"]) {
      expect(
        screen.getByRole("link", { name: `Get started with the ${plan} plan` }),
      ).toHaveAttribute("href", site.routes.signUp);
    }
  });
});

describe("navbar", () => {
  it("opens the mobile menu and closes it on Escape", async () => {
    const user = userEvent.setup();
    render(<Navbar />);
    expect(screen.queryByRole("navigation", { name: "Mobile" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open menu" }));
    const menu = screen.getByRole("navigation", { name: "Mobile" });
    expect(within(menu).getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      site.routes.signIn,
    );

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("navigation", { name: "Mobile" })).not.toBeInTheDocument();
  });
});

describe("follow-up loop", () => {
  it("raises the score on Done", async () => {
    const user = userEvent.setup();
    renderInMotion(<SaveToAction />);
    expect(screen.getByText("35%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.getByText("38%")).toBeInTheDocument();
    expect(screen.getByText(/Next up/)).toBeInTheDocument();
  });

  it("offers a smaller step on Not yet, and leaves the score alone", async () => {
    const user = userEvent.setup();
    renderInMotion(<SaveToAction />);
    await user.click(screen.getByRole("button", { name: "Not yet" }));
    expect(screen.getByText("35%")).toBeInTheDocument();
    expect(screen.getByText("Read one problem statement")).toBeInTheDocument();
  });

  it("drops the save from the total on Let go, and can be replayed", async () => {
    const user = userEvent.setup();
    renderInMotion(<SaveToAction />);
    await user.click(screen.getByRole("button", { name: "Let go" }));
    expect(screen.getByText("9 of 25 saves")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try another answer" }));
    expect(screen.getByText("9 of 26 saves")).toBeInTheDocument();
  });
});

describe("Smart Card showcase", () => {
  it("switches tabs and labels low-confidence links as unverified", async () => {
    const user = userEvent.setup();
    render(<SmartCardShowcase />);
    expect(screen.getByText("Key points")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Resources" }));
    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(screen.getByText("leetcode.com")).toBeInTheDocument();
    expect(screen.queryByText("Key points")).not.toBeInTheDocument();
  });

  it("seeks the player when a resource timestamp is clicked", async () => {
    const user = userEvent.setup();
    render(<SmartCardShowcase />);
    await user.click(screen.getByRole("tab", { name: "Resources" }));
    await user.click(screen.getByRole("button", { name: "Jump to 03:12 in the video" }));
    expect(screen.getByText("03:12 / 15:02")).toBeInTheDocument();
  });
});

describe("use cases", () => {
  it("shows a concrete after for each audience", async () => {
    const user = userEvent.setup();
    render(<UseCases />);
    expect(screen.getByText(/solve 1 problem on graphs/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Teams" }));
    expect(screen.getByText(/briefing card/)).toBeInTheDocument();
  });
});

describe("FAQ", () => {
  it("keeps every answer in the document for search engines", () => {
    render(<Faq />);
    expect(screen.getByText(/portfolio project/)).toBeInTheDocument();
    expect(screen.getByText(/must come from real search results/)).toBeInTheDocument();
  });
});
