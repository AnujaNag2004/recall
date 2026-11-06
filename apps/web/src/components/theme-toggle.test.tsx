import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { ThemeProvider } from "./theme-provider";
import { ThemeToggle } from "./theme-toggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
  });

  it("switches between light and dark and persists the choice", async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    const toggle = screen.getByRole("button", { name: "Toggle theme" });

    // The test environment reports a light system preference.
    await waitFor(() => expect(document.documentElement).toHaveClass("light"));

    await userEvent.click(toggle);
    await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
    expect(localStorage.getItem("theme")).toBe("dark");

    await userEvent.click(toggle);
    await waitFor(() => expect(document.documentElement).toHaveClass("light"));
    expect(localStorage.getItem("theme")).toBe("light");
  });
});
