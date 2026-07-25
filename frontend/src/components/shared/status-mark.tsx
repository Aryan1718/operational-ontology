type StatusMarkProps = {
  tone?: "neutral" | "warning" | "danger" | "success";
  children: React.ReactNode;
};

const TONE_CLASSNAMES = {
  neutral:
    "border-[var(--workspace-line)] bg-[var(--workspace-surface-alt)] text-[var(--workspace-muted)]",
  warning:
    "border-[var(--workspace-warning)] bg-[color:color-mix(in_srgb,var(--workspace-warning)_14%,white)] text-[var(--workspace-ink)]",
  danger:
    "border-[var(--workspace-danger)] bg-[color:color-mix(in_srgb,var(--workspace-danger)_12%,white)] text-[var(--workspace-ink)]",
  success:
    "border-[var(--workspace-success)] bg-[color:color-mix(in_srgb,var(--workspace-success)_14%,white)] text-[var(--workspace-ink)]",
};

export function StatusMark({
  tone = "neutral",
  children,
}: StatusMarkProps) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-sm border px-2 py-1 text-xs font-medium ${TONE_CLASSNAMES[tone]}`}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}
