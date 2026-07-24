/**
 * Rate limiting on public endpoints (Section 4.7). Fixed-window in-memory
 * limiter — correct for the one-container deployment of Phase 0–1; swap the
 * store when the app scales out.
 */

interface Window {
  count: number;
  resetAt: number;
}

const windows = new Map<string, Window>();

export interface RateLimitOptions {
  /** Max requests per window */
  limit: number;
  /** Window length in milliseconds */
  windowMs: number;
}

export function rateLimit(
  key: string,
  { limit, windowMs }: RateLimitOptions,
  now: number = Date.now(),
): { allowed: boolean; remaining: number; resetAt: number } {
  const existing = windows.get(key);

  if (!existing || existing.resetAt <= now) {
    windows.set(key, { count: 1, resetAt: now + windowMs });
    return { allowed: true, remaining: limit - 1, resetAt: now + windowMs };
  }

  existing.count += 1;
  const allowed = existing.count <= limit;
  return {
    allowed,
    remaining: Math.max(0, limit - existing.count),
    resetAt: existing.resetAt,
  };
}

/** Periodic cleanup to keep the map bounded */
export function pruneRateLimitWindows(now: number = Date.now()): void {
  for (const [key, window] of windows) {
    if (window.resetAt <= now) windows.delete(key);
  }
}
