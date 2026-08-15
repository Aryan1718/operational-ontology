"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SectionHeading } from "@/components/shared/section-heading";
import { StatusMark } from "@/components/shared/status-mark";
import { TechnicalLabel } from "@/components/shared/technical-label";
import {
  getActionExecution,
  getActionExecutionAuditLogs,
  searchActionExecutions,
} from "@/lib/api/action-executions";
import type { AuditLogSummary } from "@/lib/api/types";

const PAGE_LIMIT = 50;
const PLACEHOLDER = "Not available";

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

function formatOptionalValue(value: string | null | undefined) {
  if (!value) {
    return PLACEHOLDER;
  }

  return value;
}

function formatJsonValue(value: unknown) {
  if (value === null || value === undefined) {
    return PLACEHOLDER;
  }

  return JSON.stringify(value, null, 2);
}

function compareAuditLogsChronologically(auditLogA: AuditLogSummary, auditLogB: AuditLogSummary) {
  return new Date(auditLogA.timestamp).getTime() - new Date(auditLogB.timestamp).getTime();
}

function DetailField({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-3">
      <dt className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
        {label}
      </dt>
      <dd className={`mt-2 text-sm text-[var(--workspace-ink)] ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

export default function ActionExecutionsPage() {
  const [offset, setOffset] = useState(0);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);

  const { data, error, isLoading, isFetching } = useQuery({
    queryKey: ["executions", "list", PAGE_LIMIT, offset],
    queryFn: () =>
      searchActionExecutions({
        limit: PAGE_LIMIT,
        offset,
      }),
  });

  const {
    data: detail,
    error: detailError,
    isLoading: isDetailLoading,
    isFetching: isDetailFetching,
  } = useQuery({
    queryKey: ["executions", "detail", selectedExecutionId],
    queryFn: () => getActionExecution(selectedExecutionId as string),
    enabled: selectedExecutionId !== null,
  });

  const {
    data: auditData,
    error: auditError,
    isLoading: isAuditLoading,
    isFetching: isAuditFetching,
  } = useQuery({
    queryKey: ["executions", "audit-logs", selectedExecutionId],
    queryFn: () => getActionExecutionAuditLogs(selectedExecutionId as string),
    enabled: selectedExecutionId !== null,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const limit = data?.limit ?? PAGE_LIMIT;
  const showingFrom = total === 0 ? 0 : offset + 1;
  const showingTo = total === 0 ? 0 : Math.min(offset + items.length, total);
  const hasPreviousPage = offset > 0;
  const hasNextPage = offset + limit < total;
  const auditLogs = [...(auditData?.auditLogs ?? [])].sort(compareAuditLogsChronologically);

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
                      className={`border-t border-[var(--workspace-line)] align-top transition ${
                        selectedExecutionId === execution.executionId
                          ? "bg-[var(--workspace-background)]"
                          : "hover:bg-[var(--workspace-background)]"
                      }`}
                      key={execution.executionId}
                    >
                      <td className="p-0" colSpan={7}>
                        <button
                          className="grid w-full min-w-full grid-cols-[1.1fr_1.5fr_0.85fr_1fr_0.9fr_1fr_1fr] text-left"
                          onClick={() => setSelectedExecutionId(execution.executionId)}
                          type="button"
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
                        </button>
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

      <section className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-5 py-5 lg:px-6">
        <SectionHeading
          action={
            <div className="flex flex-wrap items-center gap-2">
              <TechnicalLabel>Persisted detail</TechnicalLabel>
              {isDetailFetching || isAuditFetching ? (
                <StatusMark tone="warning">Refreshing</StatusMark>
              ) : null}
            </div>
          }
          description="Selected execution details and the persisted audit records linked to that execution."
          index="06"
          title="Execution Detail"
        />

        {!selectedExecutionId ? (
          <div className="mt-5 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-10 text-sm text-[var(--workspace-muted)]">
            Select an execution to inspect its persisted details and linked audit history.
          </div>
        ) : null}

        {selectedExecutionId && isDetailLoading ? (
          <div className="mt-5 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-10 text-sm text-[var(--workspace-muted)]">
            Loading execution detail...
          </div>
        ) : null}

        {selectedExecutionId && !isDetailLoading && detailError ? (
          <div className="mt-5 border border-[var(--workspace-danger)] bg-[color:color-mix(in_srgb,var(--workspace-danger)_10%,white)] px-4 py-4 text-sm">
            <p className="font-semibold text-[var(--workspace-ink)]">
              Unable to load execution detail.
            </p>
            <p className="mt-2 text-[var(--workspace-muted)]">
              {detailError instanceof Error ? detailError.message : "Unknown API error."}
            </p>
          </div>
        ) : null}

        {selectedExecutionId && !isDetailLoading && !detailError && detail ? (
          <div className="mt-5 grid gap-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <DetailField label="Execution ID" mono value={detail.executionId} />
              <DetailField label="Action Type" value={detail.actionTypeId} />
              <DetailField label="Action Version" value={detail.actionVersion} />
              <DetailField label="Status" value={detail.status} />
              <DetailField label="Actor ID" value={detail.actor.actorId} />
              <DetailField label="Actor Role" value={detail.actor.actorRole} />
              <DetailField label="Invocation Mode" value={detail.invocationMode} />
              <DetailField
                label="Parent Execution ID"
                mono
                value={formatOptionalValue(detail.parentExecutionId)}
              />
              <DetailField label="Started" value={formatDateTime(detail.startedAt)} />
              <DetailField label="Completed" value={formatDateTime(detail.completedAt)} />
              <DetailField label="Reason" value={formatOptionalValue(detail.reason)} />
              <DetailField label="Failure Code" value={formatOptionalValue(detail.failureCode)} />
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <article className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-4">
                <h3 className="text-sm font-semibold text-[var(--workspace-ink)]">
                  Failure Message
                </h3>
                <p className="mt-3 text-sm text-[var(--workspace-muted)]">
                  {formatOptionalValue(detail.failureMessage)}
                </p>
              </article>

              <article className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-4">
                <h3 className="text-sm font-semibold text-[var(--workspace-ink)]">
                  Affected Objects
                </h3>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-[var(--workspace-muted)]">
                  {formatJsonValue(detail.affectedObjects)}
                </pre>
              </article>
            </div>

            <article className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-4">
              <h3 className="text-sm font-semibold text-[var(--workspace-ink)]">
                Result Payload
              </h3>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-[var(--workspace-muted)]">
                {formatJsonValue(detail.resultPayload)}
              </pre>
            </article>

            <article className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)]">
              <div className="border-b border-[var(--workspace-line)] px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                  Action Execution
                </p>
                <p className="mt-2 text-sm text-[var(--workspace-muted)]">{detail.executionId}</p>
                <p className="mt-3 text-sm text-[var(--workspace-ink)]">
                  Objects changed by that execution
                </p>
              </div>

              {isAuditLoading ? (
                <div className="px-4 py-10 text-sm text-[var(--workspace-muted)]">
                  Loading audit history...
                </div>
              ) : null}

              {!isAuditLoading && auditError ? (
                <div className="px-4 py-4 text-sm">
                  <p className="font-semibold text-[var(--workspace-ink)]">
                    Unable to load audit history.
                  </p>
                  <p className="mt-2 text-[var(--workspace-muted)]">
                    {auditError instanceof Error ? auditError.message : "Unknown API error."}
                  </p>
                </div>
              ) : null}

              {!isAuditLoading && !auditError && auditLogs.length === 0 ? (
                <div className="px-4 py-10 text-sm text-[var(--workspace-muted)]">
                  No audit history found for this execution.
                </div>
              ) : null}

              {!isAuditLoading && !auditError && auditLogs.length > 0 ? (
                <ol className="divide-y divide-[var(--workspace-line)]">
                  {auditLogs.map((auditLog) => (
                    <li className="grid gap-4 px-4 py-4 lg:grid-cols-[0.9fr_1.1fr]" key={auditLog.auditLogId}>
                      <div>
                        <p className="text-sm font-semibold text-[var(--workspace-ink)]">
                          {auditLog.objectType}
                        </p>
                        <p className="mt-1 font-mono text-xs text-[var(--workspace-muted)]">
                          {auditLog.objectId}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <StatusMark tone="neutral">{auditLog.actionTypeId}</StatusMark>
                          <StatusMark tone="neutral">
                            {auditLog.actorId ?? PLACEHOLDER}
                          </StatusMark>
                        </div>
                        <p className="mt-3 text-xs uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                          {formatDateTime(auditLog.timestamp)}
                        </p>
                        <p className="mt-2 text-sm text-[var(--workspace-muted)]">
                          {formatOptionalValue(auditLog.reason)}
                        </p>
                      </div>

                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                            Previous Value
                          </p>
                          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-[var(--workspace-muted)]">
                            {formatJsonValue(auditLog.previousValue)}
                          </pre>
                        </div>
                        <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                            New Value
                          </p>
                          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-[var(--workspace-muted)]">
                            {formatJsonValue(auditLog.newValue)}
                          </pre>
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : null}
            </article>
          </div>
        ) : null}
      </section>
    </div>
  );
}
