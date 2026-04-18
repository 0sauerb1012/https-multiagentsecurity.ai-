function readEnv(name: string, fallback?: string) {
  const value = process.env[name] ?? fallback;

  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }

  return value;
}

export const env = {
  siteUrl: readEnv("NEXT_PUBLIC_SITE_URL", "http://localhost:3000"),
  databaseUrl: process.env.DATABASE_URL ?? ""
};
