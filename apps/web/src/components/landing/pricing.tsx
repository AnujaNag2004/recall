import { Check } from "lucide-react";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";
import { Container, CtaLink, Panel, SectionHeading } from "./primitives";

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    blurb: "For getting your saves under control.",
    features: ["100 saves a month", "Smart Cards and tasks", "Save-to-Action score"],
  },
  {
    name: "Pro",
    price: "$8",
    period: "per month",
    blurb: "For people who save a lot and mean it.",
    features: [
      "Unlimited saves",
      "Ask Your Brain across everything",
      "Learn Mode and weekly reflections",
      "Google Calendar sync",
    ],
    highlighted: true,
  },
  {
    name: "Team",
    price: "$6",
    period: "per member, per month",
    blurb: "For small teams with a lot of meetings.",
    features: [
      "Shared workspaces and roles",
      "Action items with owners",
      "Meeting briefing cards",
      "MCP access",
    ],
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="py-20 sm:py-28">
      <Container>
        <SectionHeading
          eyebrow="Pricing"
          title="Simple plans."
          lead="This is a mock pricing table. Nothing here is for sale and nothing will charge you."
        />
        <ul className="reveal mt-12 grid gap-4 lg:grid-cols-3">
          {plans.map((plan) => (
            <li key={plan.name}>
              <Panel
                className={cn(
                  "flex h-full flex-col p-6",
                  plan.highlighted && "border-primary/50 ring-1 ring-primary/30",
                )}
              >
                <h3 className="font-semibold tracking-tight">{plan.name}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{plan.blurb}</p>
                <p className="mt-6 flex items-baseline gap-1.5">
                  <span className="text-4xl font-semibold tracking-tight">{plan.price}</span>
                  <span className="text-sm text-muted-foreground">{plan.period}</span>
                </p>
                <ul className="mt-6 mb-8 space-y-2.5 text-sm">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex gap-2">
                      <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                      {feature}
                    </li>
                  ))}
                </ul>
                <CtaLink
                  href={site.routes.signUp}
                  variant={plan.highlighted ? "default" : "outline"}
                  aria-label={`Get started with the ${plan.name} plan`}
                  className="mt-auto w-full"
                >
                  Get started
                </CtaLink>
              </Panel>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
