/**
 * Next.js instrumentation hook — starts the in-process pg-boss runner when
 * the server boots. Gated by ENABLE_JOBS so builds and tests never need a
 * database connection.
 */
export async function register() {
  if (
    process.env.NEXT_RUNTIME === "nodejs" &&
    process.env.ENABLE_JOBS === "1"
  ) {
    const { startJobs } = await import("@/jobs/start");
    await startJobs();
  }
}
