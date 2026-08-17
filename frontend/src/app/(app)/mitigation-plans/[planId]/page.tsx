"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { SectionHeading } from "@/components/shared/section-heading";
import { StatusMark } from "@/components/shared/status-mark";
import { searchAuditLogs } from "@/lib/api/audit";
import {
  getMitigationPlan,
  getMitigationPlanSteps,
  searchMitigationPlanExecutions,
  type OntologyObjectResponse,
} from "@/lib/api/mitigation-plans";

const EXECUTION_PAGE_LIMIT = 10;
const AUDIT_PAGE_LIMIT = 10;
const PLACEHOLDER = "Not available";

const LIFECYCLE_STAGES = [
  { label: "Draft", statuses: ["draft"] },
  { label: "Pending Approval", statuses: ["proposed"] },
  { label: "Approved / Rejected", statuses: ["approved", "rejected"] },
  { label: "Executing", statuses: ["executing"] },
  { label: "Completed / Failed", statuses: ["executed"] },
] as const;

function formatDateTime(value: unknown) {
  if (!value || typeof value !== "string") {
    return PLACEHOLDER;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return PLACEHOLDER;
  }

  if (typeof value === "number") {
    return new Intl.NumberFormat("en-US").format(value);
  }

  return String(value);
}

function formatCurrencyValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return PLACEHOLDER;
  }

  const numericValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numericValue)) {
    return String(value);
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(numericValue);
}

function getStatusTone(status: string | null | undefined): "neutral" | "warning" | "danger" | "success" {
  switch ((status ?? "").toLowerCase()) {
    case "approved":
    case "executed":
    case "succeeded":
      return "success";
    case "rejected":
    case "failed":
    case "cancelled":
      return "danger";
    case "proposed":
    case "executing":
    case "pending":
    case "running":
      return "warning";
    default:
      return "neutral";
  }
}

function getLifecycleTone(currentStatus: string | null, statuses: readonly string[]) {
  if (!currentStatus) {
    return "neutral" as const;
  }

  if (statuses.includes(currentStatus)) {
    return getStatusTone(currentStatus);
  }

  return "neutral" as const;
}

function getLifecycleLabel(status: string | null) {
  if (!status) {
    return "Unknown";
  }

  return status;
}

function compareSteps(stepA: OntologyObjectResponse, stepB: OntologyObjectResponse) {
  const stepOrderA = Number(stepA.properties.stepOrder ?? 0);
  const stepOrderB = Number(stepB.properties.stepOrder ?? 0);
  return stepOrderA - stepOrderB;
}

function getStepTargetObject(properties: Record<string, unknown>) {
  const candidates = [
    ["PurchaseOrder", properties.purchaseOrderId],
    ["Shipment", properties.shipmentId],
    ["Product", properties.productId],
    ["Part", properties.partId],
    ["Supplier", properties.supplierId],
    ["Target Warehouse", properties.targetWarehouseId],
  ] as const;

  const target = candidates.find(([, value]) => value);
  if (!target) {
    return PLACEHOLDER;
  }

  return `${target[0]} ${String(target[1])}`;
}

function getStepParameters(properties: Record<string, unknown>) {
  const parameters: Record<string, unknown> = {};
  for (const key of [
    "sourceWarehouseId",
    "targetWarehouseId",
    "supplierId",
    "purchaseOrderId",
    "shipmentId",
    "partId",
    "productId",
    "quantity",
    "notes",
  ]) {
    const value = properties[key];
    if (value !== null && value !== undefined && value !== "") {
      parameters[key] = value;
    }
  }

  return parameters;
}

function JsonPreview({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-[var(--workspace-muted)]">{PLACEHOLDER}</span>;
  }

  const compact = JSON.stringify(value);
  const preview = compact && compact.length > 120 ? `${compact.slice(0, 117)}...` : compact;

  return (
    <div className="space-y-2">
      <p className="break-words font-mono text-xs text-[var(--workspace-muted)]">{preview || PLACEHOLDER}</p>
      <details>
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-accent)]">
          Inspect full value
        </summary>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3 font-mono text-xs text-[var(--workspace-muted)]">
          {JSON.stringify(value, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function DetailField({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-3">
      <dt className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">{label}</dt>
      <dd className={`mt-2 text-sm text-[var(--workspace-ink)] ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}

export default function MitigationPlanDetailPage({ params }: { params: { planId: string } }) {
  const planId = params.planId;

  const {
    data: plan,
    error: planError,
    isLoading: isPlanLoading,
    isFetching: isPlanFetching,
  } = useQuery({
    queryKey: ["mitigation-plan", "detail", planId],
    queryFn: () => getMitigationPlan(planId),
  });

  const {
    data: stepData,
    error: stepError,
    isLoading: isStepLoading,
    isFetching: isStepFetching,
  } = useQuery({
    queryKey: ["mitigation-plan", "steps", planId],
    queryFn: () => getMitigationPlanSteps(planId),
  });

  const {
    data: executionData,
    error: executionError,
    isLoading: isExecutionLoading,
    isFetching: isExecutionFetching,
  } = useQuery({
    queryKey: ["mitigation-plan", "executions", planId],
    queryFn: () =>
      searchMitigationPlanExecutions({
        objectType: "MitigationPlan",
        objectId: planId,
        limit: EXECUTION_PAGE_LIMIT,
        offset: 0,
      }),
  });

  const {
    data: auditData,
    error: auditError,
    isLoading: isAuditLoading,
    isFetching: isAuditFetching,
  } = useQuery({
    queryKey: ["mitigation-plan", "audit", planId],
    queryFn: () =>
      searchAuditLogs({
        objectType: "MitigationPlan",
        objectId: planId,
        limit: AUDIT_PAGE_LIMIT,
        offset: 0,
      }),
  });

  const properties = plan?.properties ?? {};
  const currentStatus = typeof properties.status === "string" ? properties.status : null;
  const steps = [...(stepData?.objects ?? [])].sort(compareSteps);
  const executions = executionData?.items ?? [];
  const auditLogs = auditData?.data.auditLogs ?? [];

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <section className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-5 py-5 lg:px-6">
        <SectionHeading
          action={
            <div className="flex flex-wrap items-center gap-2">
              <StatusMark tone="neutral">Read only</StatusMark>
              {isPlanFetching || isStepFetching || isExecutionFetching || isAuditFetching ? (
                <StatusMark tone="warning">Refreshing</StatusMark>
              ) : null}
            </div>
          }
          description="Dedicated human review surface for one mitigation plan using authoritative object, execution, and audit records."
          index="04"
          title="Mitigation Plan Review"
        />

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Link
            className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface-alt)] px-3 py-2 text-sm font-medium text-[var(--workspace-ink)] transition hover:bg-[var(--workspace-background)]"
            href="/mitigation-plans"
          >
            Back to mitigation plans
          </Link>
          {properties.riskEventId ? (
            <Link
              className="inline-flex items-center rounded-sm border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-2 text-sm font-medium text-[var(--workspace-ink)] transition hover:bg-[var(--workspace-surface-alt)]"
              href={`/risk-events/${String(properties.riskEventId)}`}
            >
              Open Risk Event
            </Link>
          ) : null}
        </div>

        {isPlanLoading ? (
          <div className="mt-5 border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-10 text-sm text-[var(--workspace-muted)]">
            Loading mitigation plan...
          </div>
        ) : null}

        {!isPlanLoading && planError ? (
          <div className="mt-5 border border-[var(--workspace-danger)] bg-[color:color-mix(in_srgb,var(--workspace-danger)_10%,white)] px-4 py-4 text-sm">
            <p className="font-semibold text-[var(--workspace-ink)]">Unable to load mitigation plan.</p>
            <p className="mt-2 text-[var(--workspace-muted)]">{planError instanceof Error ? planError.message : "Unknown API error."}</p>
          </div>
        ) : null}

        {!isPlanLoading && !planError && plan ? (
          <div className="mt-5 grid gap-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <DetailField label="Mitigation Plan ID" mono value={formatValue(properties.mitigationPlanId)} />
              <DetailField label="Risk Event ID" mono value={formatValue(properties.riskEventId)} />
              <DetailField label="Status" value={formatValue(properties.status)} />
              <DetailField label="Estimated Cost" value={formatCurrencyValue(properties.estimatedCost)} />
              <DetailField label="Confidence Score" value={formatValue(properties.confidenceScore)} />
              <DetailField label="Approved By" mono value={formatValue(properties.approvedBy)} />
              <DetailField label="Created At" value={formatDateTime(properties.createdAt)} />
              <DetailField label="Approved At" value={formatDateTime(properties.approvedAt)} />
            </div>

            <article className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Lifecycle</p>
              <div className="mt-4 grid gap-3 lg:grid-cols-5">
                {LIFECYCLE_STAGES.map((stage) => (
                  <div key={stage.label} className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)] px-3 py-3">
                    <p className="text-sm font-semibold text-[var(--workspace-ink)]">{stage.label}</p>
                    <div className="mt-2">
                      <StatusMark tone={getLifecycleTone(currentStatus, stage.statuses)}>
                        {stage.statuses.join(" / ")}
                      </StatusMark>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <StatusMark tone={getStatusTone(currentStatus)}>
                  Current backend status: {getLifecycleLabel(currentStatus)}
                </StatusMark>
                {currentStatus === "cancelled" ? <StatusMark tone="danger">cancelled</StatusMark> : null}
              </div>
            </article>

            <article className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)]">
              <div className="border-b border-[var(--workspace-line)] px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Plan Review</p>
                <p className="mt-2 text-sm text-[var(--workspace-muted)]">
                  Generic object data currently exposes the persisted mitigation-plan properties shown below. Lifecycle action controls are not rendered because the current frontend/backend available-actions contract is not present in this codebase.
                </p>
              </div>
              <div className="grid gap-3 px-4 py-4 md:grid-cols-2">
                <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Plan Type</p>
                  <p className="mt-2 text-sm text-[var(--workspace-ink)]">{formatValue(properties.planType)}</p>
                </div>
                <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Recommended Action</p>
                  <p className="mt-2 text-sm text-[var(--workspace-ink)]">{formatValue(properties.recommendedAction)}</p>
                </div>
                <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3 md:col-span-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Explanation</p>
                  <p className="mt-2 text-sm text-[var(--workspace-ink)]">{formatValue(properties.explanation)}</p>
                </div>
                <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Created By</p>
                  <p className="mt-2 font-mono text-xs text-[var(--workspace-ink)]">{formatValue(properties.createdBy)}</p>
                </div>
                <div className="border border-[var(--workspace-line)] bg-[var(--workspace-background)] px-3 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Updated At</p>
                  <p className="mt-2 text-sm text-[var(--workspace-ink)]">{formatDateTime(properties.updatedAt)}</p>
                </div>
              </div>
            </article>

            <article className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)]">
              <div className="border-b border-[var(--workspace-line)] px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Mitigation Steps</p>
                <p className="mt-2 text-sm text-[var(--workspace-muted)]">Persisted mitigation steps linked to this plan, displayed in step order.</p>
              </div>

              {isStepLoading ? (
                <div className="px-4 py-10 text-sm text-[var(--workspace-muted)]">Loading mitigation steps...</div>
              ) : null}

              {!isStepLoading && stepError ? (
                <div className="px-4 py-4 text-sm">
                  <p className="font-semibold text-[var(--workspace-ink)]">Unable to load mitigation steps.</p>
                  <p className="mt-2 text-[var(--workspace-muted)]">{stepError instanceof Error ? stepError.message : "Unknown API error."}</p>
                </div>
              ) : null}

              {!isStepLoading && !stepError && steps.length === 0 ? (
                <div className="px-4 py-10 text-sm text-[var(--workspace-muted)]">No mitigation steps found for this plan.</div>
              ) : null}

              {!isStepLoading && !stepError && steps.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full border-collapse">
                    <thead className="bg-[var(--workspace-surface-alt)] text-left">
                      <tr>
                        {[
                          "Step",
                          "Action Type",
                          "Target Object",
                          "Parameters",
                          "Status",
                          "Execution ID",
                          "Failure Reason",
                        ].map((heading) => (
                          <th key={heading} className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">
                            {heading}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-[var(--workspace-surface)]">
                      {steps.map((step) => {
                        const stepProperties = step.properties;
                        return (
                          <tr key={step.objectId} className="border-t border-[var(--workspace-line)] align-top">
                            <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">{formatValue(stepProperties.stepOrder)}</td>
                            <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">{formatValue(stepProperties.actionType)}</td>
                            <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">{getStepTargetObject(stepProperties)}</td>
                            <td className="px-4 py-4 text-sm text-[var(--workspace-ink)]">
                              <JsonPreview value={getStepParameters(stepProperties)} />
                            </td>
                            <td className="px-4 py-4 text-sm"><StatusMark tone={getStatusTone(typeof stepProperties.status === "string" ? stepProperties.status : null)}>{formatValue(stepProperties.status)}</StatusMark></td>
                            <td className="px-4 py-4 text-sm text-[var(--workspace-muted)]">{PLACEHOLDER}</td>
                            <td className="px-4 py-4 text-sm text-[var(--workspace-muted)]">{PLACEHOLDER}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </article>

            <div className="grid gap-4 xl:grid-cols-2">
              <article className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)]">
                <div className="border-b border-[var(--workspace-line)] px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Action Execution History</p>
                  <p className="mt-2 text-sm text-[var(--workspace-muted)]">Existing governed action executions filtered to this mitigation plan object.</p>
                </div>

                {isExecutionLoading ? <div className="px-4 py-10 text-sm text-[var(--workspace-muted)]">Loading execution history...</div> : null}

                {!isExecutionLoading && executionError ? (
                  <div className="px-4 py-4 text-sm">
                    <p className="font-semibold text-[var(--workspace-ink)]">Unable to load execution history.</p>
                    <p className="mt-2 text-[var(--workspace-muted)]">{executionError instanceof Error ? executionError.message : "Unknown API error."}</p>
                  </div>
                ) : null}

                {!isExecutionLoading && !executionError && executions.length === 0 ? (
                  <div className="px-4 py-10 text-sm text-[var(--workspace-muted)]">No action executions found for this mitigation plan.</div>
                ) : null}

                {!isExecutionLoading && !executionError && executions.length > 0 ? (
                  <ol className="divide-y divide-[var(--workspace-line)]">
                    {executions.map((execution) => (
                      <li key={execution.executionId} className="px-4 py-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-[var(--workspace-ink)]">{execution.actionTypeId}</p>
                            <p className="mt-1 font-mono text-xs text-[var(--workspace-muted)]">{execution.executionId}</p>
                          </div>
                          <StatusMark tone={getStatusTone(execution.status)}>{execution.status}</StatusMark>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-[var(--workspace-muted)]">
                          <span>{formatDateTime(execution.startedAt)}</span>
                          <span>{execution.actor.actorId}</span>
                          <Link className="text-[var(--workspace-accent)] underline-offset-2 hover:underline" href={`/action-executions/${execution.executionId}`}>
                            Open execution
                          </Link>
                        </div>
                      </li>
                    ))}
                  </ol>
                ) : null}
              </article>

              <article className="border border-[var(--workspace-line)] bg-[var(--workspace-surface)]">
                <div className="border-b border-[var(--workspace-line)] px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Audit History</p>
                  <p className="mt-2 text-sm text-[var(--workspace-muted)]">Existing audit records filtered to this mitigation plan object.</p>
                </div>

                {isAuditLoading ? <div className="px-4 py-10 text-sm text-[var(--workspace-muted)]">Loading audit history...</div> : null}

                {!isAuditLoading && auditError ? (
                  <div className="px-4 py-4 text-sm">
                    <p className="font-semibold text-[var(--workspace-ink)]">Unable to load audit history.</p>
                    <p className="mt-2 text-[var(--workspace-muted)]">{auditError instanceof Error ? auditError.message : "Unknown API error."}</p>
                  </div>
                ) : null}

                {!isAuditLoading && !auditError && auditLogs.length === 0 ? (
                  <div className="px-4 py-10 text-sm text-[var(--workspace-muted)]">No audit history found for this mitigation plan.</div>
                ) : null}

                {!isAuditLoading && !auditError && auditLogs.length > 0 ? (
                  <ol className="divide-y divide-[var(--workspace-line)]">
                    {auditLogs.map((auditLog) => (
                      <li key={auditLog.auditLogId} className="px-4 py-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-[var(--workspace-ink)]">{auditLog.actionTypeId}</p>
                            <p className="mt-1 font-mono text-xs text-[var(--workspace-muted)]">{auditLog.objectId}</p>
                          </div>
                          <span className="text-xs uppercase tracking-[0.16em] text-[var(--workspace-muted)]">{formatDateTime(auditLog.timestamp)}</span>
                        </div>
                        <div className="mt-3 grid gap-3 md:grid-cols-2">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">Previous Value</p>
                            <JsonPreview value={auditLog.previousValue} />
                          </div>
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--workspace-muted)]">New Value</p>
                            <JsonPreview value={auditLog.newValue} />
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-[var(--workspace-muted)]">
                          <span>{formatValue(auditLog.actorId)}</span>
                          <span>{formatValue(auditLog.reason)}</span>
                          {auditLog.executionId ? (
                            <Link className="text-[var(--workspace-accent)] underline-offset-2 hover:underline" href={`/action-executions/${auditLog.executionId}`}>
                              Open execution
                            </Link>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ol>
                ) : null}
              </article>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
