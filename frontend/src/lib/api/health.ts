import { apiRequest } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";

export function getHealth() {
  return apiRequest<HealthResponse>("/health");
}
