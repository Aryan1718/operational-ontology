import { TechnicalLabel } from "@/components/shared/technical-label";

type WorkspaceHeaderProps = {
  breadcrumbs: string[];
  sectionTitle: string;
};

export function WorkspaceHeader({
  breadcrumbs,
  sectionTitle,
}: WorkspaceHeaderProps) {
  return (
    <header className="sticky top-0 z-10 border-b border-[var(--workspace-line)] bg-[color:color-mix(in_srgb,var(--workspace-background)_90%,white)]/95 backdrop-blur-sm">
      <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--workspace-muted)]">
            {breadcrumbs.map((crumb, index) => (
              <span className="flex items-center gap-2" key={`${crumb}-${index}`}>
                {index > 0 ? (
                  <span aria-hidden="true" className="font-mono text-[10px]">
                    /
                  </span>
                ) : null}
                <span
                  className={
                    index === breadcrumbs.length - 1
                      ? "text-[var(--workspace-ink)]"
                      : ""
                  }
                >
                  {crumb}
                </span>
              </span>
            ))}
          </div>
          <div className="mt-2 flex items-center gap-3">
            <h1 className="text-lg font-semibold tracking-[0.01em]">
              {sectionTitle}
            </h1>
            <TechnicalLabel>Workspace shell</TechnicalLabel>
          </div>
        </div>

        <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center">
          <button
            aria-label="Search ontology"
            className="inline-flex min-h-10 items-center gap-3 rounded-md border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-2 text-sm text-[var(--workspace-muted)] transition hover:border-[var(--workspace-accent)] hover:text-[var(--workspace-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--workspace-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--workspace-background)]"
            type="button"
          >
            <span aria-hidden="true" className="font-mono text-xs">
              /
            </span>
            <span>Search ontology</span>
          </button>

          <div className="rounded-md border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-2 text-sm">
            <p className="font-medium text-[var(--workspace-ink)]">Workspace</p>
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
              Authenticated shell
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
