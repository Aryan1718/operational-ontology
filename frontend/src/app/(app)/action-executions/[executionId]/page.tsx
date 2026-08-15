"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { SectionHeading } from "@/components/shared/section-heading";
import { StatusMark } from "@/components/shared/status-mark";
import { TechnicalLabel } from "@/components/shared/technical-label";
import {
  getActionExecution,
  getActionExecutionAuditLogs,
} from "@/lib/api/action-executions";
import type { AuditLogSummary } from "@/lib/api/types";

const PLACEHOLDER = "Not available";
const POLL_INTERVAL_MS = 5000;

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not completed";
  }

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

function formatJsonValue(value: unknown) {
  if (value === null || value === undefined) {
    return PLACEHOLDER;
  }

  return JSON.stringify(value, null, 2);
}

function compareAuditLogsChronologically(auditLogA: AuditLogSummary, auditLogB: AuditLogSummary) {
  return new Date(auditLogA.timestamp).getTime() - new Date(auditLogB.timestamp).getTime();
}

function isTerminalExecutionStatus(status: string) {
  const normalizedStatus = status.toLowerCase();

  return normalizedStatus === "succeeded" || normalizedStatus === "failed" || normalizedStatus === "rejected";
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

export default function ActionExecutionDetailPage({
  params,
}: {
  params: { executionId: string };
}) {
  const executionId = params.executionId;

  const {
    data: detail,
    error: detailError,
    isLoading: isDetailLoading,
    isFetching: isDetailFetching,
  } = useQuery({
    queryKey: ["executions", "detail", executionId],
    queryFn: () => getActionExecution(executionId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;

      if (!status) {
        return false;
      }

      return isTerminalExecutionStatus(status) ? false : POLL_INTERVAL_MS;
    },
  });

  const {
    data: auditData,
    error: auditError,
    isLoading: isAuditLoading,
    isFetching: isAuditFetching,
  } = useQuery({
    queryKey: ["executions", "audit-logs", executionId],
    queryFn: () => getActionExecutionAuditLogs(executionId),
  });

  const auditLogs = [...(auditData?.auditLogs ?? [])].sort(compareAuditLogsChronologically);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
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

        <div className="mt-5">
          <Link
            className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface-alt)] px-3 py-2 text-sm font-medium text-[var(--workspace-ink)] transition hover:bg-[var(--workspace-background)]"
            href="/action-executions"
          >
            Back to executions
          </Link>
        </div>

        {isDetailLoading ? (
          <div className="mt-5 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-10 text-sm text-[var(--workspace-muted)]">
            Loading execution detail...
          </div>
        ) : null}

        {!isDetailLoading && detailError ? (
          <div className="mt-5 border border-[var(--workspace-danger)] bg-[color:color-mix(in_srgb,var(--workspace-danger)_10%,white)] px-4 py-4 text-sm">
            <p className="font-semibold text-[var(--workspace-ink)]">
              Unable to load execution detail.
            </p>
            <p className="mt-2 text-[var(--workspace-muted)]">
              {detailError instanceof Error ? detailError.message : "Unknown API error."}
            </p>
          </div>
        ) : null}

        {!isDetailLoading && !detailError && detail ? (
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
            </div>

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
