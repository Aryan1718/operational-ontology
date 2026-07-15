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
