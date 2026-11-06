"use client";

import { ArrowRight } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Container, Panel, SectionHeading } from "./primitives";

const cases = [
  {
    id: "students",
    label: "Students",
    who: "Priya, final-year CS student. Exam in 9 days.",
    before: [
      "23 DSA videos in a playlist she never reopens",
      "Lecture PDFs spread across three folders",
      "A vague plan to “revise everything” next weekend",
    ],
    after: [
      "Summaries and flashcards for each lecture and video",
      "A revision plan that works back from her exam date",
      "One nudge tonight: solve 1 problem on graphs",
    ],
  },
  {
    id: "professionals",
    label: "Professionals",
    who: "Arjun, product manager. Saves things at midnight.",
    before: [
      "Recipes he has saved and never cooked",
      "Workout reels that didn't turn into workouts",
      "Finance threads he means to read “someday”",
    ],
    after: [
      "A grocery list made from the recipe, ready for Sunday",
      "A 5-minute workout scheduled before his first meeting",
      "A score showing he acts on cooking, and not on fitness",
    ],
  },
  {
    id: "teams",
    label: "Teams",
    who: "A five-person startup with a client call at 3.",
    before: [
      "Meeting notes nobody turns into tasks",
      "“What did the client say about pricing?” asked in chat, again",
      "Ten minutes of tab-hunting before each call",
    ],
    after: [
      "Action items with owners and due dates, pulled from the notes",
      "That question answered with citations to the source",
      "A briefing card ready before the meeting starts",
    ],
  },
];

export function UseCases() {
  return (
    <section id="use-cases" className="border-y bg-muted/40 py-20 sm:py-28">
      <Container>
        <SectionHeading eyebrow="Use cases" title="Same pile of saves. A different week." />
        <Tabs defaultValue="students" className="reveal mt-10 gap-6">
          <TabsList className="group-data-horizontal/tabs:h-10">
            {cases.map((useCase) => (
              <TabsTrigger key={useCase.id} value={useCase.id} className="px-2.5 sm:px-4">
                {useCase.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {cases.map((useCase) => (
            <TabsContent key={useCase.id} value={useCase.id}>
              <p className="text-base text-muted-foreground">{useCase.who}</p>
              <div className="mt-4 grid grid-cols-1 items-stretch gap-3 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
                <div className="rounded-2xl border border-dashed p-6">
                  <h3 className="font-medium text-muted-foreground">Before</h3>
                  <ul className="mt-3 space-y-2.5 text-[15px] text-muted-foreground">
                    {useCase.before.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <ArrowRight
                  aria-hidden
                  className="mx-auto hidden size-5 self-center text-muted-foreground md:block"
                />
                <Panel className="p-6">
                  <h3 className="font-medium text-primary">With Recall</h3>
                  <ul className="mt-3 space-y-2.5 text-[15px]">
                    {useCase.after.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </Panel>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </Container>
    </section>
  );
}
