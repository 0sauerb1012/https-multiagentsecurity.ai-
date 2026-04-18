import { env } from "@/lib/env";

export type DatabaseClient = {
  query<T>(sql: string, params?: unknown[]): Promise<T[]>;
};

export function getDb(): DatabaseClient {
  if (!env.databaseUrl) {
    throw new Error(
      "DATABASE_URL is not configured. Replace the mock query modules before using getDb()."
    );
  }

  return {
    async query<T>() {
      void env.databaseUrl;
      throw new Error("Database client is not implemented yet.");
    }
  };
}
