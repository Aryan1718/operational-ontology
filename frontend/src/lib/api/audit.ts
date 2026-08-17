import { apiRequest } from "@/lib/api/client";
import type { ApiSuccessEnvelope, AuditLogSummary } from "@/lib/api/types";

export type AuditLogSearchRequest = {
  limit: number;
  offset: number;
  objectType?: string;
  objectId?: string;
  actorId?: string;
  actionTypeId?: string;
};

export type AuditLogListResponse = {
  auditLogs: AuditLogSummary[];
};

function buildAuditSearchQuery(request: AuditLogSearchRequest) {
  const searchParams = new URLSearchParams({
    limit: String(request.limit),
    offset: String(request.offset),
  });

  if (request.objectType) {
    searchParams.set("objectType", request.objectType);
  }

  if (request.objectId) {
    searchParams.set("objectId", request.objectId);
  }

  if (request.actorId) {
    searchParams.set("actorId", request.actorId);
  }

  if (request.actionTypeId) {
    searchParams.set("actionTypeId", request.actionTypeId);
  }

  return searchParams.toString();
}

export async function searchAuditLogs(request: AuditLogSearchRequest) {
  const query = buildAuditSearchQuery(request);

  return apiRequest<ApiSuccessEnvelope<AuditLogListResponse>>(`/api/v1/audit?${query}`);
}
