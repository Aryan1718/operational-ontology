import type { ReactNode } from "react";

type SectionHeadingProps = {
  index: string;
  title: string;
  description?: string;
  action?: ReactNode;
};

export function SectionHeading({
  index,
  title,
  description,
  action,
}: SectionHeadingProps) {
  return (
    <div className="flex flex-col gap-3 border-b border-[var(--workspace-line)] pb-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-[var(--workspace-muted)]">
          {index}
        </p>
        <h2 className="mt-2 text-xl font-semibold">{title}</h2>
        {description ? (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--workspace-muted)]">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}
