import { Faq } from "@/components/landing/faq";
import { FeatureGrid } from "@/components/landing/feature-grid";
import { FinalCta, Footer } from "@/components/landing/footer";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { MotionProvider } from "@/components/landing/motion-provider";
import { Navbar } from "@/components/landing/navbar";
import { Pricing } from "@/components/landing/pricing";
import { ProblemStrip } from "@/components/landing/problem-strip";
import { SaveToAction } from "@/components/landing/save-to-action";
import { SmartCardShowcase } from "@/components/landing/smart-card-showcase";
import { UnderTheHood } from "@/components/landing/under-the-hood";
import { UseCases } from "@/components/landing/use-cases";

export default function LandingPage() {
  return (
    <MotionProvider>
      <a
        href="#main"
        className="sr-only z-[60] rounded-lg bg-background px-3 py-2 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <Navbar />
      <main id="main">
        <Hero />
        <ProblemStrip />
        <HowItWorks />
        <SaveToAction />
        <SmartCardShowcase />
        <UseCases />
        <FeatureGrid />
        <UnderTheHood />
        <Pricing />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </MotionProvider>
  );
}
