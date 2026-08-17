"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SectionHeading } from "@/components/shared/section-heading";
import { StatusMark } from "@/components/shared/status-mark";
import { TechnicalLabel } from "@/components/shared/technical-label";
import { searchAuditLogs } from "@/lib/api/audit";

const PAGE_LIMIT = 20;
const PLACEHOLDER = "Not available";

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatOptionalValue(value: string | null | undefined) {
  if (!value) {
    return PLACEHOLDER;
  }

  return value;
}

function formatJsonPreview(value: unknown) {
  if (value === null || value === undefined) {
    return PLACEHOLDER;
  }

  const compact = JSON.stringify(value);
  if (!compact) {
    return PLACEHOLDER;
  }

  return compact.length > 120 ? `${compact.slice(0, 117)}...` : compact;
}

function formatJsonValue(value: unknown) {
  if (value === null || value === undefined) {
    return PLACEHOLDER;
  }

  return JSON.stringify(value, null, 2);
}

function JsonValueCell({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  return (
    <div className="space-y-2">
      <p className="break-words font-mono text-xs text-[var(--workspace-muted)]">
        {formatJsonPreview(value)}
      </p>
      <details>
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-accent)]">
          Inspect full {label}
        </summary>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3 font-mono text-xs text-[var(--workspace-muted)]">
          {formatJsonValue(value)}
        </pre>
      </details>
    </div>
  );
}

export default function AuditPage() {
  const [offset, setOffset] = useState(0);
  const [appliedObjectType, setAppliedObjectType] = useState("");
  const [appliedObjectId, setAppliedObjectId] = useState("");
  const [appliedActionType, setAppliedActionType] = useState("");
  const [appliedActor, setAppliedActor] = useState("");
  const [draftObjectType, setDraftObjectType] = useState("");
  const [draftObjectId, setDraftObjectId] = useState("");
  const [draftActionType, setDraftActionType] = useState("");
  const [draftActor, setDraftActor] = useState("");

  const filters = {
    objectType: appliedObjectType || undefined,
    objectId: appliedObjectId || undefined,
    actionTypeId: appliedActionType || undefined,
    actorId: appliedActor || undefined,
  };

  const { data, error, isLoading, isFetching } = useQuery({
    queryKey: ["audit", "list", PAGE_LIMIT, offset, filters],
    queryFn: () =>
      searchAuditLogs({
        limit: PAGE_LIMIT,
        offset,
        ...filters,
      }),
  });

  const auditLogs = data?.data.auditLogs ?? [];
  const totalKnown = offset + auditLogs.length;
  const hasMore = Boolean(data?.meta.hasMore);
  const showingFrom = auditLogs.length === 0 ? 0 : offset + 1;
  const showingTo = auditLogs.length === 0 ? 0 : offset + auditLogs.length;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <section className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-5 py-5 lg:px-6">
        <SectionHeading
          action={
            <div className="flex flex-wrap items-center gap-2">
              <TechnicalLabel>Read only</TechnicalLabel>
              {isFetching && !isLoading ? <StatusMark tone="warning">Refreshing</StatusMark> : null}
            </div>
          }
          description="Authoritative backend audit history with filterable change records and execution links."
          index="06"
          title="Audit Log"
        />

        <form
          className="mt-5 grid gap-3 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-4 md:grid-cols-2 xl:grid-cols-4"
          onSubmit={(event) => {
            event.preventDefault();
            setAppliedObjectType(draftObjectType.trim());
            setAppliedObjectId(draftObjectId.trim());
            setAppliedActionType(draftActionType.trim());
            setAppliedActor(draftActor.trim());
            setOffset(0);
          }}
        >
          <label className="grid gap-2 text-sm text-[var(--workspace-ink)]">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
              Object Type
            </span>
            <input
              className="rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-2 text-sm text-[var(--workspace-ink)] outline-none transition focus:border-[var(--workspace-accent)]"
              onChange={(event) => setDraftObjectType(event.target.value)}
              value={draftObjectType}
            />
          </label>
          <label className="grid gap-2 text-sm text-[var(--workspace-ink)]">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
              Object ID
            </span>
            <input
              className="rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-2 text-sm text-[var(--workspace-ink)] outline-none transition focus:border-[var(--workspace-accent)]"
              onChange={(event) => setDraftObjectId(event.target.value)}
              value={draftObjectId}
            />
          </label>
          <label className="grid gap-2 text-sm text-[var(--workspace-ink)]">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
              Action Type
            </span>
            <input
              className="rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-2 text-sm text-[var(--workspace-ink)] outline-none transition focus:border-[var(--workspace-accent)]"
              onChange={(event) => setDraftActionType(event.target.value)}
              value={draftActionType}
            />
          </label>
          <label className="grid gap-2 text-sm text-[var(--workspace-ink)]">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
              Actor
            </span>
            <input
              className="rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-2 text-sm text-[var(--workspace-ink)] outline-none transition focus:border-[var(--workspace-accent)]"
              onChange={(event) => setDraftActor(event.target.value)}
              value={draftActor}
            />
          </label>
          <div className="flex flex-wrap items-center gap-3 md:col-span-2 xl:col-span-4">
            <button
              className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface-alt)] px-3 py-2 text-sm font-medium text-[var(--workspace-ink)] transition hover:bg-[var(--workspace-surface)]"
              type="submit"
            >
              Apply filters
            </button>
            <button
              className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-2 text-sm font-medium text-[var(--workspace-ink)] transition hover:bg-[var(--workspace-surface-alt)]"
              onClick={() => {
                setDraftObjectType("");
                setDraftObjectId("");
                setDraftActionType("");
                setDraftActor("");
                setAppliedObjectType("");
                setAppliedObjectId("");
                setAppliedActionType("");
                setAppliedActor("");
                setOffset(0);
              }}
              type="button"
            >
              Clear
            </button>
          </div>
        </form>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusMark tone="neutral">Page size {PAGE_LIMIT}</StatusMark>
            <StatusMark tone="neutral">Showing {showingFrom}-{showingTo}</StatusMark>
          </div>
          <p className="text-sm text-[var(--workspace-muted)]">
            {hasMore ? `At least ${totalKnown} records available` : `${totalKnown} records loaded`}
          </p>
        </div>

        {isLoading ? (
          <div className="mt-5 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-10 text-sm text-[var(--workspace-muted)]">
            Loading audit history...
          </div>
        ) : null}

        {!isLoading && error ? (
          <div className="mt-5 border border-[var(--workspace-danger)] bg-[color:color-mix(in_srgb,var(--workspace-danger)_10%,white)] px-4 py-4 text-sm">
            <p className="font-semibold text-[var(--workspace-ink)]">Unable to load audit history.</p>
            <p className="mt-2 text-[var(--workspace-muted)]">
              {error instanceof Error ? error.message : "Unknown API error."}
            </p>
          </div>
        ) : null}

        {!isLoading && !error && auditLogs.length === 0 ? (
          <div className="mt-5 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-10 text-sm text-[var(--workspace-muted)]">
            No audit history matched the current filters.
          </div>
        ) : null}

        {!isLoading && !error && auditLogs.length > 0 ? (
          <div className="mt-5 overflow-hidden border border-[var(--workspace-line)]">
            <div className="overflow-x-auto">
              <table className="min-w-[1300px] border-collapse">
                <thead className="bg-[var(--workspace-surface-alt)] text-left">
                  <tr>
                    {[
                      "Timestamp",
                      "Actor",
                      "Action Type",
                      "Object Type",
                      "Object ID",
                      "Previous Value",
                      "New Value",
                      "Reason",
                      "Execution ID",
                    ].map((heading) => (
                      <th
                        className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]"
                        key={heading}
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-[var(--workspace-surface)]">
                  {auditLogs.map((auditLog) => (
                    <tr
                      className="border-t border-[var(--workspace-line)] align-top"
                      key={auditLog.auditLogId}
                    >
                      <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                        {formatDateTime(auditLog.timestamp)}
                      </td>
                      <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                        {formatOptionalValue(auditLog.actorId)}
                      </td>
                      <td className="px-4 py-4 text-sm">
                        <StatusMark tone="neutral">{auditLog.actionTypeId}</StatusMark>
                      </td>
                      <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                        {auditLog.objectType}
                      </td>
                      <td className="px-4 py-4 font-mono text-xs text-[var(--workspace-ink)]">
                        {auditLog.objectId}
                      </td>
                      <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                        <JsonValueCell label="previous value" value={auditLog.previousValue} />
                      </td>
                      <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                        <JsonValueCell label="new value" value={auditLog.newValue} />
                      </td>
                      <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                        {formatOptionalValue(auditLog.reason)}
                      </td>
                      <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                        {auditLog.executionId ? (
                          <Link
                            className="font-mono text-xs text-[var(--workspace-accent)] underline-offset-2 hover:underline"
                            href={`/action-executions/${auditLog.executionId}`}
                          >
                            {auditLog.executionId}
                          </Link>
                        ) : (
                          <span className="text-[var(--workspace-muted)]">{PLACEHOLDER}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        <div className="mt-5 flex items-center justify-between gap-3 border-t border-[var(--workspace-line)] pt-4">
          <button
            className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface-alt)] px-3 py-2 text-sm font-medium text-[var(--workspace-ink)] transition disabled:cursor-not-allowed disabled:opacity-50"
            disabled={offset === 0}
            onClick={() => setOffset((currentOffset) => Math.max(0, currentOffset - PAGE_LIMIT))}
            type="button"
          >
            Previous
          </button>
          <button
            className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface-alt)] px-3 py-2 text-sm font-medium text-[var(--workspace-ink)] transition disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!hasMore}
            onClick={() => setOffset((currentOffset) => currentOffset + PAGE_LIMIT)}
            type="button"
          >
            Next
          </button>
        </div>
      </section>
    </div>
  );
}
