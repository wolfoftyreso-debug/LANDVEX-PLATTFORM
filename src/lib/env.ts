import { z } from "zod";

/** Zod-validated environment (Section 3). Secrets come from SSM/Secrets
 * Manager at deploy time — never from files in the repo. */
const envSchema = z.object({
  DATABASE_URL: z
    .string()
    .default("postgres://baltic:baltic@localhost:5432/baltic_bridge"),
  AUTH_SECRET: z.string().default("dev-only-change-me"),
  S3_ENDPOINT: z.string().optional(),
  S3_REGION: z.string().default("eu-north-1"),
  S3_ACCESS_KEY_ID: z.string().optional(),
  S3_SECRET_ACCESS_KEY: z.string().optional(),
  S3_DOCUMENTS_BUCKET: z.string().default("documents"),
  S3_FORCE_PATH_STYLE: z.coerce.boolean().default(false),
  EMAIL_PROVIDER: z.enum(["console", "ses", "smtp"]).default("console"),
  EMAIL_FROM: z.string().default("no-reply@balticbridge.example"),
  SMTP_HOST: z.string().optional(),
  SMTP_PORT: z.coerce.number().int().default(587),
  SMTP_SECURE: z.coerce.boolean().default(false),
  SMTP_USER: z.string().optional(),
  SMTP_PASSWORD: z.string().optional(),
  NODE_ENV: z
    .enum(["development", "test", "production"])
    .default("development"),
});

export const env = envSchema.parse(process.env);
