import type { Metadata } from "next";
import { Suspense } from "react";
import { SmartCard } from "@/components/saves/smart-card";

export const metadata: Metadata = { title: "Smart Card" };

export default function SavePage() {
  return (
    <Suspense>
      <SmartCard />
    </Suspense>
  );
}
