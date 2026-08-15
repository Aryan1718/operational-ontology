import { apiRequestData } from "@/lib/api/client";
import type {
  ActionExecutionAuditLogResponse,
  ActionExecutionDetail,
  ActionExecutionSearchRequest,
  ActionExecutionSearchResponse,
} from "@/lib/api/types";

export function searchActionExecutions(request: ActionExecutionSearchRequest) {
  return apiRequestData<ActionExecutionSearchResponse>(
    "/api/v1/action-executions/search",
    {
      method: "POST",
      json: request,
    },
  );
}

export function getActionExecution(executionId: string) {
  return apiRequestData<ActionExecutionDetail>(
    `/api/v1/action-executions/${executionId}`,
  );
}

export function getActionExecutionAuditLogs(executionId: string) {
  return apiRequestData<ActionExecutionAuditLogResponse>(
    `/api/v1/action-executions/${executionId}/audit-logs`,
  );
}
