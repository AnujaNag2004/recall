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
};

export const mainNav: NavItem[] = [
  {
    href: "/home",
    label: "Home",
    icon: Home,
  },
  {
    href: "/inbox",
    label: "Inbox",
    icon: Inbox,
  },
  {
    href: "/ask",
    label: "Ask",
    icon: MessageCircle,
  },
  {
    href: "/library",
    label: "Library",
    icon: BookOpen,
  },
  {
    href: "/graph",
    label: "Graph",
    icon: Network,
  },
  {
    href: "/learn",
    label: "Learn",
    icon: GraduationCap,
  },
  {
    href: "/tasks",
    label: "Tasks",
    icon: CheckSquare,
  },
  {
    href: "/insights",
    label: "Insights",
    icon: BarChart3,
  },
];

export const settingsNav: NavItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
};

export const allNav = [...mainNav, settingsNav];
