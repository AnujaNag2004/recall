"use client";

import { LogOut, Menu, PanelLeftClose, PanelLeftOpen, Plus, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, Suspense, useEffect, useState, useSyncExternalStore } from "react";
import { Wordmark } from "@/components/landing/primitives";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ApiError } from "@/lib/api/client";
import { mainNav, type NavItem, settingsNav } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { signOut, useMe } from "./app-context";
import { CommandPalette } from "./command-palette";
import { WorkspaceSwitcher } from "./workspace-switcher";

const COLLAPSED_KEY = "recall.sidebarCollapsed";
const collapsedListeners = new Set<() => void>();

function readCollapsed() {
  try {
    return window.localStorage.getItem(COLLAPSED_KEY) === "true";
  } catch {
    return false;
  }
}

function writeCollapsed(value: boolean) {
  try {
    window.localStorage.setItem(COLLAPSED_KEY, String(value));
  } catch {
    // Only this visit will remember it.
  }
  for (const listener of collapsedListeners) listener();
}

/** Reads localStorage without a hydration mismatch: the server always renders expanded. */
function useSidebarCollapsed() {
  return useSyncExternalStore(
    (listener) => {
      collapsedListeners.add(listener);
      return () => collapsedListeners.delete(listener);
    },
    readCollapsed,
    () => false,
  );
}

function NavLink({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? item.label : undefined}
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors",
        active
          ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
          : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        collapsed && "justify-center px-0",
      )}
    >
      <item.icon className="size-4 shrink-0" aria-hidden />
      {!collapsed && item.label}
    </Link>
  );
}

function SidebarNav({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  return (
    <nav aria-label="App" className="flex flex-1 flex-col gap-0.5">
      {mainNav.map((item) => (
        <NavLink key={item.href} item={item} collapsed={collapsed} onNavigate={onNavigate} />
      ))}
      <div className="mt-auto">
        <NavLink item={settingsNav} collapsed={collapsed} onNavigate={onNavigate} />
      </div>
    </nav>
  );
}

function UserMenu() {
  const { data: me } = useMe();
  const label = me?.user.name || me?.user.email || "Account";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className="flex size-10 items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex size-8 items-center justify-center rounded-full bg-muted text-sm font-medium">
          {label[0].toUpperCase()}
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="truncate">{me?.user.email ?? label}</DropdownMenuLabel>
          <DropdownMenuItem onClick={() => void signOut()}>
            <LogOut aria-hidden />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Free hosting puts the API to sleep, so a slow first load gets an explanation. */
function ServerStatus() {
  const { isPending, isError, error, refetch } = useMe();
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!isPending) return;
    const timer = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(timer);
  }, [isPending]);

  useEffect(() => {
    // The session ended somewhere else; nothing in the app can work without one.
    if (error instanceof ApiError && error.status === 401) void signOut();
  }, [error]);

  if (isError && !(error instanceof ApiError && error.status === 401)) {
    return (
      <div role="alert" className="flex items-center gap-3 border-b bg-muted px-4 py-2 text-sm">
        We can&apos;t reach the server right now.
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Try again
        </Button>
      </div>
    );
  }
  if (isPending && slow) {
    return (
      <div role="status" className="border-b bg-muted px-4 py-2 text-sm text-muted-foreground">
        Waking up the server. This can take up to a minute on the free tier.
      </div>
    );
  }
  return null;
}

export function AppShell({ children }: { children: ReactNode }) {
  const collapsed = useSidebarCollapsed();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside
        className={cn(
          "hidden shrink-0 flex-col gap-4 border-r bg-sidebar p-3 text-sidebar-foreground transition-[width] duration-200 md:flex",
          collapsed ? "w-16" : "w-60",
        )}
      >
        <div className={cn("flex h-10 items-center", collapsed ? "justify-center" : "px-2")}>
          <Link href="/home" aria-label="Recall home" className="rounded-md">
            <Wordmark markOnly={collapsed} />
          </Link>
        </div>
        <WorkspaceSwitcher collapsed={collapsed} />
        {/* The current URL isn't known while prerendering dynamic routes like /saves/[id]. */}
        <Suspense fallback={<div className="flex-1" />}>
          <SidebarNav collapsed={collapsed} />
        </Suspense>
        <Button
          variant="ghost"
          size="icon"
          className={cn("size-9 text-muted-foreground", !collapsed && "self-end")}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          onClick={() => writeCollapsed(!collapsed)}
        >
          {collapsed ? <PanelLeftOpen aria-hidden /> : <PanelLeftClose aria-hidden />}
        </Button>
      </aside>

      <Dialog open={drawerOpen} onOpenChange={setDrawerOpen}>
        <DialogContent
          className="top-0 left-0 flex h-dvh w-72 max-w-[85vw] translate-x-0 translate-y-0 flex-col gap-4 rounded-none bg-sidebar p-3 sm:max-w-72"
        >
          <DialogTitle className="flex h-10 items-center px-2">
            <Wordmark />
          </DialogTitle>
          <WorkspaceSwitcher />
          <Suspense fallback={<div className="flex-1" />}>
            <SidebarNav onNavigate={() => setDrawerOpen(false)} />
          </Suspense>
        </DialogContent>
      </Dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-3 sm:px-4">
          <Button
            variant="ghost"
            size="icon"
            className="size-10 md:hidden"
            aria-label="Open navigation"
            onClick={() => setDrawerOpen(true)}
          >
            <Menu aria-hidden />
          </Button>
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-lg border bg-background px-3 text-sm text-muted-foreground outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring sm:max-w-xs"
          >
            <Search className="size-4 shrink-0" aria-hidden />
            <span className="truncate">Search or jump to…</span>
            <kbd className="ml-auto hidden font-sans text-xs sm:inline">⌘K</kbd>
          </button>
          <div className="ml-auto flex shrink-0 items-center gap-1">
            <Link
              href="/inbox"
              aria-label="Quick save"
              className="flex h-9 items-center gap-1.5 rounded-lg bg-primary px-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:px-3"
            >
              <Plus className="size-4" aria-hidden />
              <span className="hidden sm:inline">Quick save</span>
            </Link>
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <ServerStatus />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
