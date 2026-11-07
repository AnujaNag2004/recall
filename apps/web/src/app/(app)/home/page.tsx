import type { Metadata } from "next";
import { HomeView } from "@/components/app/home-view";

export const metadata: Metadata = { title: "Home" };

export default function HomePage() {
  return <HomeView />;
}
