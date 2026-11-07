import {
  BarChart3,
  BookOpen,
  CheckSquare,
  GraduationCap,
  Home,
  Inbox,
  type LucideIcon,
  MessageCircle,
  Network,
  Settings,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** The friendly empty state, until the phase that builds this page. */
  emptyTitle: string;
  emptyBody: string;
};

export const mainNav: NavItem[] = [
  {
    href: "/home",
    label: "Home",
    icon: Home,
    emptyTitle: "",
    emptyBody: "",
  },
  {
    href: "/inbox",
    label: "Inbox",
    icon: Inbox,
    emptyTitle: "Capture is on its way",
    emptyBody: "You'll paste links and drop files here, then watch each one become a Smart Card.",
  },
  {
    href: "/ask",
    label: "Ask",
    icon: MessageCircle,
    emptyTitle: "Ask Your Brain is on its way",
    emptyBody: "You'll chat with everything you've saved here, with answers that cite their sources.",
  },
  {
    href: "/library",
    label: "Library",
    icon: BookOpen,
    emptyTitle: "Your library is on its way",
    emptyBody: "Every save will live here, ready to filter and search.",
  },
  {
    href: "/graph",
    label: "Graph",
    icon: Network,
    emptyTitle: "The Knowledge Graph is on its way",
    emptyBody: "You'll see your topics and how they connect here.",
  },
  {
    href: "/learn",
    label: "Learn",
    icon: GraduationCap,
    emptyTitle: "Learn Mode is on its way",
    emptyBody: "Flashcards and quizzes made from your saves will appear here.",
  },
  {
    href: "/tasks",
    label: "Tasks",
    icon: CheckSquare,
    emptyTitle: "Tasks are on their way",
    emptyBody: "The small next steps from your saves will line up here.",
  },
  {
    href: "/insights",
    label: "Insights",
    icon: BarChart3,
    emptyTitle: "Insights are on their way",
    emptyBody: "Your Save-to-Action score and weekly reflections will appear here.",
  },
];

export const settingsNav: NavItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
  emptyTitle: "Settings are on their way",
  emptyBody: "You'll manage your profile, connected accounts and data here.",
};

export const allNav = [...mainNav, settingsNav];
