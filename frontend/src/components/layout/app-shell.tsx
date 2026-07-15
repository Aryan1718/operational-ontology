import type { ReactNode } from "react";
import Link from "next/link";

const navigation = [
  { href: "/", label: "Command Center" },
  { href: "/ontology", label: "Ontology Studio" },
  { href: "/explorer", label: "Object Explorer" },
  { href: "/risk-events", label: "Risk Events" },
  { href: "/mitigation-plans", label: "Mitigation Plans" },
  { href: "/action-executions", label: "Action Executions" },
  { href: "/audit", label: "Audit Log" },
  { href: "/assistant", label: "AI Assistant" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <div className="mx-auto grid min-h-screen max-w-7xl gap-6 px-4 py-4 lg:grid-cols-[280px_1fr] lg:px-6">
        <aside className="rounded-[2rem] border border-border bg-white/90 p-5 shadow-sm">
          <div className="mb-6">
            <p className="font-display text-2xl">Ontology Platform</p>
            <p className="text-sm text-stone-600">
              Navigation placeholders for the planned operational surfaces.
            </p>
          </div>
          <nav className="grid gap-2">
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-2xl px-4 py-3 text-sm font-semibold transition hover:bg-accent hover:text-white"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>
        <div className="rounded-[2rem] border border-border bg-white/70 p-4 shadow-sm md:p-8">
          {children}
        </div>
      </div>
    </div>
  );
}
