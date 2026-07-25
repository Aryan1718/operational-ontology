"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { WorkspaceHeader } from "@/components/layout/workspace-header";
import { WorkspaceSidebar } from "@/components/layout/workspace-sidebar";

type AppShellProps = {
  children: ReactNode;
};

const SECTION_TITLES: Record<string, string> = {
  "/": "Overview",
  "/ontology": "Ontology",
  "/objects": "Objects",
  "/risk-events": "Risk Desk",
  "/mitigation-plans": "Mitigation Queue",
  "/action-executions": "Executions",
  "/audit": "Audit Trail",
};

function getSectionTitle(pathname: string) {
  const match = Object.entries(SECTION_TITLES).find(
    ([route]) => pathname === route || pathname.startsWith(`${route}/`),
  );

  return match?.[1] ?? "Workspace";
}

function getBreadcrumbs(pathname: string) {
  if (pathname === "/") {
    return ["Workspace", "Overview"];
  }

  const segments = pathname.split("/").filter(Boolean);

  return [
    "Workspace",
    ...segments.map((segment) => segment.replace(/-/g, " ")),
  ];
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const sectionTitle = getSectionTitle(pathname);
  const breadcrumbs = getBreadcrumbs(pathname);

  return (
    <div className="min-h-screen bg-[var(--workspace-background)] text-[var(--workspace-ink)]">
      <div className="grid min-h-screen lg:grid-cols-[auto_1fr]">
        <WorkspaceSidebar />
        <div className="min-w-0">
          <WorkspaceHeader
            breadcrumbs={breadcrumbs}
            sectionTitle={sectionTitle}
          />
          <main className="min-w-0 px-4 py-4 sm:px-6 sm:py-5 lg:px-8">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
