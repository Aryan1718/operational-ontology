export type HealthResponse = {
  status: string;
  service: string;
  database: {
    configured: boolean;
    driver: string | null;
    host: string | null;
    port: number | null;
    database: string | null;
  };
};

export type ApiResponseMeta = {
  requestId: string;
  timestamp: string;
  nextCursor?: string | null;
  hasMore?: boolean | null;
};

export type ApiSuccessEnvelope<T> = {
  data: T;
  meta: ApiResponseMeta;
};

export type ActionExecutionActorSummary = {
  actorId: string;
  actorRole: string;
};

export type ActionExecutionSummary = {
  executionId: string;
  actionTypeId: string;
  status: string;
  actor: ActionExecutionActorSummary;
  invocationMode: string;
  parentExecutionId: string | null;
  startedAt: string;
  completedAt: string | null;
  failureCode: string | null;
  failureMessage: string | null;
};

export type ActionExecutionSearchRequest = {
  limit: number;
  offset: number;
};

export type ActionExecutionSearchResponse = {
  items: ActionExecutionSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type ActionExecutionDetail = {
  executionId: string;
  actionTypeId: string;
  actionVersion: string;
  status: string;
  actor: ActionExecutionActorSummary;
  invocationMode: string;
  parentExecutionId: string | null;
  reason: string | null;
  startedAt: string;
  completedAt: string | null;
  resultPayload: unknown | null;
  failureCode: string | null;
  failureMessage: string | null;
  affectedObjects: Array<Record<string, string>> | null;
};

export type AuditLogSummary = {
  auditLogId: string;
  actionTypeId: string;
  actorId: string | null;
  executionId: string | null;
  objectType: string;
  objectId: string;
  previousValue: Record<string, unknown> | null;
  newValue: Record<string, unknown> | null;
  reason: string | null;
  timestamp: string;
};

export type ActionExecutionAuditLogResponse = {
  auditLogs: AuditLogSummary[];
};
