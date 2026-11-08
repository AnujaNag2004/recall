import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnswerText, parseBlocks } from "./answer-text";
import type { SourceRef } from "./use-ask";

const source = (number: number): SourceRef => ({
  number,
  kind: "save",
  title: `Source ${number} title`,
  snippet: "",
  save_id: "s",
  start_ts: null,
  url: null,
});

describe("parseBlocks", () => {
  it("separates headings, lists and paragraphs", () => {
    const blocks = parseBlocks("### Plan\n* one\n* two\n\n1. first\n2. second\nPlain text.");
    expect(blocks.map((b) => b.kind)).toEqual(["heading", "ul", "ol", "p"]);
  });
});

describe("AnswerText", () => {
  it("renders Markdown without showing the symbols", () => {
    const { container } = render(
      <AnswerText content={"### Tips\n* **Be specific** about it"} sources={[]} onOpen={vi.fn()} />,
    );
    expect(container.textContent).not.toMatch(/[#*]/);
    expect(screen.getByText("Be specific").tagName).toBe("STRONG");
    expect(container.querySelectorAll("li")).toHaveLength(1);
  });

  it("turns single and grouped citations into chips", () => {
    render(
      <AnswerText content="One [1], both [1, 2], and [3]." sources={[source(1), source(2)]} onOpen={vi.fn()} />,
    );
    expect(screen.getAllByRole("button", { name: /Source 1:/ })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /Source 2:/ })).toHaveLength(1);
    // A number with no matching source is left as written.
    expect(screen.getByText(/\[3\]/)).toBeInTheDocument();
  });

  it("never renders HTML from the answer", () => {
    const { container } = render(
      <AnswerText content={'<img src=x onerror="alert(1)"> **<b>hi</b>**'} sources={[]} onOpen={vi.fn()} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain("<img");
  });
});
