import type { ReactNode } from "react";

export function TechnicalLabel({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface-alt)] px-2 py-1 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
      {children}
    </span>
  );
}
