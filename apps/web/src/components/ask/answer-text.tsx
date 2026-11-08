import { Fragment, type ReactNode } from "react";
import type { SourceRef } from "./use-ask";

/**
 * Renders a model's answer: the small subset of Markdown models actually use (headings,
 * lists, bold, inline code) plus citation chips. It builds React elements and never sets
 * HTML, so anything a model or a saved page slips into an answer stays plain text.
 */

type Cite = (source: SourceRef) => void;

// [3], [2, 4] and [2][4] all become chips.
const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[\d{1,2}(?:\s*,\s*\d{1,2})*\])/g;

function Chip({ source, onOpen }: { source: SourceRef; onOpen: Cite }) {
  return (
    <button
      type="button"
      title={source.title}
      aria-label={`Source ${source.number}: ${source.title}`}
      onClick={() => onOpen(source)}
      className="mx-0.5 inline-flex size-5 items-center justify-center rounded-md bg-primary/10 align-text-top text-[11px] font-medium text-primary hover:bg-primary/20"
    >
      {source.number}
    </button>
  );
}

export function renderInline(
  text: string,
  sources: SourceRef[] | undefined,
  onOpen: Cite,
): ReactNode[] {
  return text.split(INLINE).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={index} className="font-semibold text-foreground">
          {renderInline(part.slice(2, -2), sources, onOpen)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={index} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    const cite = part.match(/^\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]$/);
    if (cite) {
      const found = cite[1]
        .split(",")
        .map((n) => sources?.find((s) => s.number === Number(n.trim())))
        .filter((s): s is SourceRef => Boolean(s));
      // An unknown number stays visible as written rather than vanishing.
      if (found.length === 0) return <Fragment key={index}>{part}</Fragment>;
      return (
        <Fragment key={index}>
          {found.map((source) => (
            <Chip key={source.number} source={source} onOpen={onOpen} />
          ))}
        </Fragment>
      );
    }
    return <Fragment key={index}>{part}</Fragment>;
  });
}

type Block =
  | { kind: "heading"; text: string }
  | { kind: "ul" | "ol"; items: string[] }
  | { kind: "p"; lines: string[] };

export function parseBlocks(content: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of content.split("\n")) {
    const line = raw.trimEnd();
    const heading = line.match(/^\s{0,3}#{1,6}\s+(.*)$/);
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d{1,3}[.)]\s+(.*)$/);
    const last = blocks.at(-1);
    if (!line.trim()) {
      blocks.push({ kind: "p", lines: [] });
    } else if (heading) {
      blocks.push({ kind: "heading", text: heading[1] });
    } else if (bullet || numbered) {
      const kind = bullet ? "ul" : "ol";
      const text = (bullet ?? numbered)![1];
      if (last?.kind === kind) last.items.push(text);
      else blocks.push({ kind, items: [text] });
    } else if (last?.kind === "p") {
      last.lines.push(line);
    } else if ((last?.kind === "ul" || last?.kind === "ol") && /^\s{2,}\S/.test(raw)) {
      // An indented line continues the list item above it.
      last.items[last.items.length - 1] += ` ${line.trim()}`;
    } else {
      blocks.push({ kind: "p", lines: [line] });
    }
  }
  return blocks.filter((b) => b.kind !== "p" || b.lines.length > 0);
}

export function AnswerText({
  content,
  sources,
  onOpen,
}: {
  content: string;
  sources: SourceRef[] | undefined;
  onOpen: Cite;
}) {
  const inline = (text: string) => renderInline(text, sources, onOpen);
  return (
    <div className="space-y-3">
      {parseBlocks(content).map((block, index) => {
        if (block.kind === "heading") {
          return (
            <p key={index} className="pt-1 font-semibold text-foreground">
              {inline(block.text)}
            </p>
          );
        }
        if (block.kind === "p") {
          return (
            <p key={index} className="whitespace-pre-line">
              {inline(block.lines.join("\n"))}
            </p>
          );
        }
        const List = block.kind === "ul" ? "ul" : "ol";
        return (
          <List
            key={index}
            className={`space-y-1.5 pl-5 ${block.kind === "ul" ? "list-disc" : "list-decimal"} marker:text-muted-foreground`}
          >
            {block.items.map((item, i) => (
              <li key={i}>{inline(item)}</li>
            ))}
          </List>
        );
      })}
    </div>
  );
}
