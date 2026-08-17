import { apiRequestData } from "@/lib/api/client";
import type { ActionExecutionSearchResponse } from "@/lib/api/types";

export type OntologyObjectResponse = {
  objectType: string;
  objectId: string;
  displayName: string | null;
  properties: Record<string, unknown>;
};

export type LinkedObjectsResponse = {
  source: {
    objectType: string;
    objectId: string;
  };
  linkType: string;
  targetObjectType: string;
  cardinality: string;
  objects: OntologyObjectResponse[];
};

export type MitigationPlanExecutionSearchRequest = {
  objectType: string;
  objectId: string;
  limit: number;
  offset: number;
};

export function getMitigationPlan(planId: string) {
  return apiRequestData<OntologyObjectResponse>(`/api/v1/objects/MitigationPlan/${planId}`);
}

export function getMitigationPlanSteps(planId: string) {
  return apiRequestData<LinkedObjectsResponse>(
    `/api/v1/objects/MitigationPlan/${planId}/links/mitigationPlanToMitigationSteps`,
  );
}

export function searchMitigationPlanExecutions(request: MitigationPlanExecutionSearchRequest) {
  return apiRequestData<ActionExecutionSearchResponse>("/api/v1/action-executions/search", {
    method: "POST",
    json: request,
  });
}
