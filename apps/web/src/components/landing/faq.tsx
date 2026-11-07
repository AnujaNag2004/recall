import { Plus } from "lucide-react";
import { Container, SectionHeading } from "./primitives";

const questions = [
  {
    q: "Who makes Recall?",
    a: "Anuja builds it independently, to production standards. It runs on free infrastructure, so the server can take a minute to wake up, and AI use has a daily limit. There's nothing to pay for: the pricing above is a mock.",
  },
  {
    q: "What can I save?",
    a: "Links from YouTube, X, Instagram, LinkedIn and Reddit, articles, PDFs, images and screenshots, voice notes, plain text and pasted emails.",
  },
  {
    q: "How is this different from a bookmarking or notes app?",
    a: "Those stop at saving. Recall turns a save into a small next step, follows up to ask whether you did it, and measures how often your saves lead to action.",
  },
  {
    q: "Does the AI make up links?",
    a: "It isn't allowed to. Links in the Resource Panel must come from real search results and pass verification. Anything that can't be confirmed is labeled unverified.",
  },
  {
    q: "Will Recall do things without asking me?",
    a: "No. Anything that reaches outside Recall, like adding a Google Calendar event or sending an email, is proposed first and only runs after you approve it.",
  },
  {
    q: "Is my data private?",
    a: "Every workspace is isolated by row-level security in the database, as well as by checks in the API. Saved content is sent to AI providers to process it, with email addresses and phone numbers removed first. You can export your data or delete your account from Settings at any time.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="py-20 sm:py-28">
      <Container className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] lg:gap-16">
        <SectionHeading eyebrow="FAQ" title="Questions, answered." />
        {/* Native <details> needs no JavaScript and keeps answers in the HTML for search. */}
        <div className="reveal divide-y border-y">
          {questions.map(({ q, a }) => (
            <details key={q} className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-md py-4 font-medium [&::-webkit-details-marker]:hidden">
                {q}
                <Plus
                  aria-hidden
                  className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-45"
                />
              </summary>
              <p className="pb-5 text-[15px] leading-relaxed text-pretty text-muted-foreground">{a}</p>
            </details>
          ))}
        </div>
      </Container>
    </section>
  );
}
