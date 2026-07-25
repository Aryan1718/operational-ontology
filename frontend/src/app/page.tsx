import { AppShell } from "@/components/layout/app-shell";
import { SectionHeading } from "@/components/shared/section-heading";
import { StatusMark } from "@/components/shared/status-mark";
import { TechnicalLabel } from "@/components/shared/technical-label";

const VOCABULARY = [
  "Objects",
  "Relationships",
  "Functions",
  "Governed actions",
  "Permissions",
  "Execution evidence",
];

const WORKFLOW = [
  "Supplier delay",
  "Affected parts",
  "Exposed products",
  "At-risk orders",
  "Inventory options",
  "Mitigation decision",
  "Approved execution",
  "Audit evidence",
];

const WORKSPACE_AREAS = [
  ["Ontology", "Inspect the operational model and its declared controls."],
  ["Objects", "Inspect business object instances once object browsing is added."],
  ["Risk Desk", "Investigate disruption cases and their downstream exposure."],
  ["Mitigation Queue", "Review proposed responses before governed approval."],
  ["Executions", "Inspect governed operations and their execution records."],
  ["Audit Trail", "Verify what changed, who changed it, and why."],
] as const;

export default function HomePage() {
  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <section className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)]">
          <div className="grid gap-6 px-5 py-5 lg:grid-cols-[1.25fr_0.75fr] lg:px-6">
            <div className="space-y-4">
              <TechnicalLabel>Section 00 / Operations Desk</TechnicalLabel>
              <div className="space-y-3">
                <h2 className="text-3xl font-semibold tracking-[-0.02em] sm:text-[2.2rem]">
                  Operations Desk
                </h2>
                <p className="max-w-3xl text-sm leading-6 text-[var(--workspace-muted)] sm:text-base">
                  The application connects operational objects, relationships,
                  functions, governed actions, and execution evidence into one
                  inspectable working model.
                </p>
              </div>
            </div>

            <div className="grid gap-3 border-l-0 border-[var(--workspace-line)] pt-1 lg:border-l lg:pl-6">
              <div className="flex flex-wrap gap-2">
                <StatusMark tone="neutral">Metadata-led interface</StatusMark>
                <StatusMark tone="warning">No live operational data</StatusMark>
              </div>
              <dl className="grid gap-2 text-sm">
                <div className="flex items-center justify-between border-b border-[var(--workspace-line)] pb-2">
                  <dt className="text-[var(--workspace-muted)]">Shell scope</dt>
                  <dd className="font-mono text-xs uppercase tracking-[0.16em]">
                    Frontend increment 01
                  </dd>
                </div>
                <div className="flex items-center justify-between border-b border-[var(--workspace-line)] pb-2">
                  <dt className="text-[var(--workspace-muted)]">Primary surface</dt>
                  <dd className="font-medium">Authenticated workspace</dd>
                </div>
                <div className="flex items-center justify-between pb-1">
                  <dt className="text-[var(--workspace-muted)]">Current focus</dt>
                  <dd className="font-medium">Overview and shell</dd>
                </div>
              </dl>
            </div>
          </div>
        </section>

        <section className="grid gap-px overflow-hidden border border-[var(--workspace-line)] bg-[var(--workspace-line)] lg:grid-cols-[0.9fr_1.1fr]">
          <div className="bg-[var(--workspace-surface)] px-5 py-5 lg:px-6">
            <SectionHeading
              description="The vocabulary below describes the structural layers the workspace will inspect."
              index="01"
              title="Operational model"
            />
            <ol className="mt-5 grid gap-2">
              {VOCABULARY.map((item, index) => (
                <li
                  className="flex items-center justify-between border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3"
                  key={item}
                >
                  <span className="font-mono text-xs uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="flex-1 px-4 text-sm font-medium">{item}</span>
                  <TechnicalLabel>Layer</TechnicalLabel>
                </li>
              ))}
            </ol>
          </div>

          <div className="bg-[var(--workspace-surface)] px-5 py-5 lg:px-6">
            <SectionHeading
              description="The core disruption path is shown as an operational sequence. This increment establishes only the visual frame."
              index="02"
              title="Disruption workflow"
            />
            <ol className="mt-5 flex flex-wrap gap-2">
              {WORKFLOW.map((step, index) => (
                <li
                  className="flex items-center gap-2 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3 text-sm"
                  key={step}
                >
                  <span className="font-mono text-xs uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span>{step}</span>
                  {index < WORKFLOW.length - 1 ? (
                    <span
                      aria-hidden="true"
                      className="ml-1 font-mono text-xs text-[var(--workspace-accent)]"
                    >
                      -&gt;
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-5 py-5 lg:px-6">
          <SectionHeading
            description="Each workspace area has a narrow operational purpose rather than a generic dashboard role."
            index="03"
            title="Workspace map"
          />
          <div className="mt-5 grid gap-px border border-[var(--workspace-line)] bg-[var(--workspace-line)] md:grid-cols-2">
            {WORKSPACE_AREAS.map(([title, description], index) => (
              <article
                className="bg-[var(--workspace-background)] px-4 py-4"
                key={title}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--workspace-muted)]">
                      {String(index + 1).padStart(2, "0")}
                    </p>
                    <h3 className="mt-2 text-base font-semibold">{title}</h3>
                  </div>
                  <TechnicalLabel>Area</TechnicalLabel>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--workspace-muted)]">
                  {description}
                </p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
