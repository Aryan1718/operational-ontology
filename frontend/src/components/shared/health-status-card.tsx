"use client";

import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api/health";

export function HealthStatusCard() {
  const { data, error, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  return (
    <div className="rounded-[1.75rem] border border-border bg-stone-950 p-6 text-stone-50">
      <p className="font-display text-2xl">Backend handshake</p>
      <p className="mt-2 text-sm text-stone-300">
        The frontend checks the API health endpoint through the shared client layer.
      </p>
      {isLoading ? (
        <p className="mt-6 rounded-2xl bg-white/10 px-4 py-3 text-sm">
          Checking backend status...
        </p>
      ) : null}
      {isError ? (
        <div className="mt-6 rounded-2xl border border-red-400/40 bg-red-950/40 px-4 py-3 text-sm">
          <p className="font-semibold">Backend unavailable</p>
          <p>{error instanceof Error ? error.message : "Unknown error"}</p>
        </div>
      ) : null}
      {data ? (
        <div className="mt-6 space-y-2 rounded-2xl bg-emerald-950/70 px-4 py-4 text-sm">
          <p className="font-semibold text-emerald-200">Status: {data.status}</p>
          <p>Service: {data.service}</p>
          <p>
            Database config:{" "}
            {data.database.configured ? "configured" : "not configured"}
          </p>
        </div>
      ) : null}
    </div>
  );
}
