"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useWorkspaces } from "./app-context";

export function WorkspaceSwitcher({ collapsed = false }: { collapsed?: boolean }) {
  const { workspaces, active, setActive } = useWorkspaces();

  if (!active) return <Skeleton className="h-10 w-full rounded-lg" />;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`Workspace: ${active.name}. Switch workspace`}
        className="flex h-10 w-full items-center gap-2 rounded-lg px-2 text-left text-sm font-medium outline-none hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span
          aria-hidden
          className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary text-xs font-semibold text-primary-foreground"
        >
          {active.name[0]}
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1 truncate">{active.name}</span>
            <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
          {workspaces.map((workspace) => (
            <DropdownMenuItem key={workspace.id} onClick={() => setActive(workspace.id)}>
              <span className="min-w-0 flex-1 truncate">{workspace.name}</span>
              <Check
                aria-hidden
                className={cn("size-4", workspace.id !== active.id && "invisible")}
              />
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
