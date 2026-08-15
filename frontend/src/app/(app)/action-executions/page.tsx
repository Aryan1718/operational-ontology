"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SectionHeading } from "@/components/shared/section-heading";
import { StatusMark } from "@/components/shared/status-mark";
import { TechnicalLabel } from "@/components/shared/technical-label";
import { searchActionExecutions } from "@/lib/api/action-executions";

const PAGE_LIMIT = 50;

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not completed";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getStatusTone(status: string): "neutral" | "warning" | "danger" | "success" {
  switch (status.toLowerCase()) {
    case "succeeded":
      return "success";
    case "failed":
    case "rejected":
      return "danger";
    case "started":
    case "running":
    case "pending":
      return "warning";
    default:
      return "neutral";
  }
}

export default function ActionExecutionsPage() {
  const [offset, setOffset] = useState(0);

  const { data, error, isLoading, isFetching } = useQuery({
    queryKey: ["executions", "list", PAGE_LIMIT, offset],
    queryFn: () =>
      searchActionExecutions({
        limit: PAGE_LIMIT,
        offset,
      }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const limit = data?.limit ?? PAGE_LIMIT;
  const showingFrom = total === 0 ? 0 : offset + 1;
  const showingTo = total === 0 ? 0 : Math.min(offset + items.length, total);
  const hasPreviousPage = offset > 0;
  const hasNextPage = offset + limit < total;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <section className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-5 py-5 lg:px-6">
        <SectionHeading
          action={
            <div className="flex flex-wrap items-center gap-2">
              <TechnicalLabel>Read only</TechnicalLabel>
              {isFetching && !isLoading ? (
                <StatusMark tone="warning">Refreshing</StatusMark>
              ) : null}
            </div>
          }
          description="Persisted governed action executions returned from the backend search endpoint."
          index="05"
          title="Action Execution History"
        />

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusMark tone="neutral">Page size {limit}</StatusMark>
            <StatusMark tone="neutral">Total {total}</StatusMark>
          </div>
          <p className="text-sm text-[var(--workspace-muted)]">
            Showing {showingFrom}-{showingTo} of {total}
          </p>
        </div>

        {isLoading ? (
          <div className="mt-5 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-10 text-sm text-[var(--workspace-muted)]">
            Loading action execution history...
          </div>
        ) : null}

        {!isLoading && error ? (
          <div className="mt-5 border border-[var(--workspace-danger)] bg-[color:color-mix(in_srgb,var(--workspace-danger)_10%,white)] px-4 py-4 text-sm">
            <p className="font-semibold text-[var(--workspace-ink)]">
              Unable to load action execution history.
            </p>
            <p className="mt-2 text-[var(--workspace-muted)]">
              {error instanceof Error ? error.message : "Unknown API error."}
            </p>
          </div>
        ) : null}

        {!isLoading && !error && items.length === 0 ? (
          <div className="mt-5 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-10 text-sm text-[var(--workspace-muted)]">
            No action execution history found.
          </div>
        ) : null}

        {!isLoading && !error && items.length > 0 ? (
          <div className="mt-5 overflow-hidden border border-[var(--workspace-line)]">
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse">
                <thead className="bg-[var(--workspace-surface-alt)] text-left">
                  <tr>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                      Action
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                      Execution ID
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                      Status
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                      Actor
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                      Invocation
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                      Started
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                      Completed
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-[var(--workspace-surface)]">
                  {items.map((execution) => (
                    <tr
                      className="border-t border-[var(--workspace-line)] align-top transition hover:bg-[var(--workspace-background)]"
                      key={execution.executionId}
                    >
                      <td className="p-0" colSpan={7}>
                        <Link
                          className="grid w-full min-w-full grid-cols-[1.1fr_1.5fr_0.85fr_1fr_0.9fr_1fr_1fr] text-left"
                          href={`/action-executions/${execution.executionId}`}
                        >
                          <span className="px-4 py-4 text-sm font-medium">
                            <span className="block">{execution.actionTypeId}</span>
                            {execution.parentExecutionId ? (
                              <span className="mt-1 block font-mono text-xs text-[var(--workspace-muted)]">
                                Parent {execution.parentExecutionId}
                              </span>
                            ) : null}
                          </span>
                          <span className="px-4 py-4 font-mono text-xs text-[var(--workspace-ink)]">
                            {execution.executionId}
                          </span>
                          <span className="px-4 py-4 text-sm">
                            <StatusMark tone={getStatusTone(execution.status)}>
                              {execution.status}
                            </StatusMark>
                          </span>
                          <span className="px-4 py-4 text-sm">
                            <span className="block">{execution.actor.actorId}</span>
                            <span className="mt-1 block text-xs text-[var(--workspace-muted)]">
                              {execution.actor.actorRole}
                            </span>
                          </span>
                          <span className="px-4 py-4 text-sm">{execution.invocationMode}</span>
                          <span className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                            {formatDateTime(execution.startedAt)}
                          </span>
                          <span className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                            {formatDateTime(execution.completedAt)}
                          </span>
                        </Link>
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
            disabled={!hasPreviousPage}
            onClick={() => setOffset((currentOffset) => Math.max(0, currentOffset - limit))}
            type="button"
          >
            Previous
          </button>
          <button
            className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface-alt)] px-3 py-2 text-sm font-medium text-[var(--workspace-ink)] transition disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!hasNextPage}
            onClick={() => setOffset((currentOffset) => currentOffset + limit)}
            type="button"
          >
            Next
          </button>
        </div>
      </section>
    </div>
  );
}
