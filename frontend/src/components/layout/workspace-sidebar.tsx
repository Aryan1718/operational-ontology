"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavigationEntry = {
  href: string;
  label: string;
  code: string;
  available: boolean;
};

const NAVIGATION: NavigationEntry[] = [
  { href: "/", label: "Overview", code: "00", available: true },
  { href: "/ontology", label: "Ontology", code: "01", available: true },
  { href: "/objects", label: "Objects", code: "02", available: false },
  { href: "/risk-events", label: "Risk Desk", code: "03", available: false },
  {
    href: "/mitigation-plans",
    label: "Mitigation Queue",
    code: "04",
    available: false,
  },
  {
    href: "/action-executions",
    label: "Executions",
    code: "05",
    available: true,
  },
  { href: "/audit", label: "Audit Trail", code: "06", available: true },
];

function NavigationItem({
  item,
  collapsed,
  active,
}: {
  item: NavigationEntry;
  collapsed: boolean;
  active: boolean;
}) {
  const baseClassName =
    "group flex items-center gap-3 rounded-md border px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--workspace-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--workspace-rail)]";

  const code = (
    <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--workspace-rail-muted)]">
      {item.code}
    </span>
  );

  const content = (
    <>
      <span className="flex w-9 shrink-0 items-center justify-between">
        <span
          aria-hidden="true"
          className="h-2 w-2 rounded-full border border-[var(--workspace-rail-line)] bg-[var(--workspace-rail-muted)]"
        />
        {!collapsed ? code : null}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{item.label}</span>
        {!collapsed ? (
          <span className="block text-xs text-[var(--workspace-rail-muted)]">
            {item.available ? "Available" : "Unavailable"}
          </span>
        ) : null}
      </span>
    </>
  );

  if (!item.available) {
    return (
      <div
        aria-disabled="true"
        className={`${baseClassName} cursor-not-allowed border-[var(--workspace-rail-line)] text-[var(--workspace-rail-muted)] opacity-80`}
        title={`${item.label} is not part of this increment`}
      >
        {content}
      </div>
    );
  }

  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={`${baseClassName} ${
        active
          ? "border-[var(--workspace-accent)] bg-[var(--workspace-rail-active)] text-[var(--workspace-rail-ink)]"
          : "border-transparent text-[var(--workspace-rail-ink)] hover:border-[var(--workspace-rail-line)] hover:bg-[var(--workspace-rail-hover)]"
      }`}
      href={item.href}
    >
      {content}
    </Link>
  );
}

export function WorkspaceSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className="border-r border-[var(--workspace-line)] bg-[var(--workspace-rail)] text-[var(--workspace-rail-ink)]">
      <div
        className={`sticky top-0 flex h-screen flex-col ${
          collapsed ? "w-[88px]" : "w-[296px]"
        } transition-[width] duration-200`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--workspace-rail-line)] px-4 py-4">
          <div className={collapsed ? "sr-only" : "min-w-0"}>
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-[var(--workspace-rail-muted)]">
              Operational Ontology
            </p>
            <p className="mt-2 text-lg font-semibold leading-5">
              Ontology Manager
            </p>
          </div>
          <button
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-[var(--workspace-rail-line)] text-sm text-[var(--workspace-rail-ink)] transition hover:bg-[var(--workspace-rail-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--workspace-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--workspace-rail)]"
            onClick={() => setCollapsed((value) => !value)}
            type="button"
          >
            {collapsed ? ">>" : "<<"}
          </button>
        </div>

        <nav aria-label="Primary" className="flex-1 px-3 py-4">
          <div className="mb-3 px-1">
            <p
              className={`font-mono text-[11px] uppercase tracking-[0.22em] text-[var(--workspace-rail-muted)] ${
                collapsed ? "sr-only" : ""
              }`}
            >
              Navigation
            </p>
          </div>
          <div className="space-y-2">
            {NAVIGATION.map((item) => (
              <NavigationItem
                key={item.href}
                active={item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)}
                collapsed={collapsed}
                item={item}
              />
            ))}
          </div>
        </nav>

        <div className="border-t border-[var(--workspace-rail-line)] px-4 py-4">
          <div
            className={`rounded-md border border-[var(--workspace-rail-line)] bg-[var(--workspace-rail-panel)] px-3 py-3 ${
              collapsed ? "text-center" : ""
            }`}
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--workspace-rail-muted)]">
              Scope
            </p>
            <p
              className={`mt-2 text-sm ${
                collapsed ? "sr-only" : "text-[var(--workspace-rail-ink)]"
              }`}
            >
              Visual shell only. Operational routes remain unavailable until their workflows exist.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
