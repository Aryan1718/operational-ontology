import { getHealth } from "@/lib/api/health";

describe("getHealth", () => {
  it("requests the backend health endpoint through the API client", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "ok",
        service: "ontology-api",
        database: {
          configured: true,
          driver: "postgresql+psycopg",
          host: "localhost",
          port: 5432,
          database: "ontology_dev",
        },
      }),
    });

    vi.stubGlobal("fetch", fetchMock);

    const response = await getHealth();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/health", {
      headers: expect.any(Headers),
      body: undefined,
    });
    expect(response.status).toBe("ok");

    vi.unstubAllGlobals();
  });
});
