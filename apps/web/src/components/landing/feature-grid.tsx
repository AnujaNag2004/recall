import { AlarmClock, Brain, GraduationCap, Network, Plug, Users } from "lucide-react";
import { Container, SectionHeading } from "./primitives";

const features = [
  {
    icon: Brain,
    title: "Ask Your Brain",
    body: "Chat with everything you've saved and get answers that cite their sources.",
  },
  {
    icon: AlarmClock,
    title: "Just-in-time recall",
    body: "The right save comes back before the exam, the meeting or the grocery run.",
  },
  {
    icon: Network,
    title: "Knowledge Graph",
    body: "See your topics connected, including your obsessions and your blind spots.",
  },
  {
    icon: GraduationCap,
    title: "Learn Mode",
    body: "Flashcards and quizzes from any save, scheduled with spaced repetition.",
  },
  {
    icon: Users,
    title: "Teams",
    body: "Shared workspaces with roles, action items with owners, and meeting briefings.",
  },
  {
    icon: Plug,
    title: "MCP integration",
    body: "Search your saves and tasks from any MCP client, using your own API key.",
  },
];

export function FeatureGrid() {
  return (
    <section id="features" className="py-20 sm:py-28">
      <Container>
        <SectionHeading eyebrow="Features" title="One place for what you meant to get back to." />
        {/* The 1px gap over a border-colored background draws the hairlines. */}
        <ul className="reveal mt-12 grid gap-px overflow-hidden rounded-2xl border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <li key={feature.title} className="bg-card p-6 sm:p-8">
              <feature.icon className="size-5 text-primary" aria-hidden />
              <h3 className="mt-4 font-semibold tracking-tight">{feature.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{feature.body}</p>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
