import { describe, expect, it } from "vitest";
import { pruneRateLimitWindows, rateLimit } from "./rate-limit";

describe("rate limiter", () => {
  const opts = { limit: 3, windowMs: 60_000 };

  it("allows up to the limit within a window", () => {
    const key = `k1-${Math.random()}`;
    const t0 = 1_000_000;
    expect(rateLimit(key, opts, t0).allowed).toBe(true);
    expect(rateLimit(key, opts, t0 + 1).allowed).toBe(true);
    expect(rateLimit(key, opts, t0 + 2).allowed).toBe(true);
    expect(rateLimit(key, opts, t0 + 3).allowed).toBe(false);
  });

  it("resets after the window elapses", () => {
    const key = `k2-${Math.random()}`;
    const t0 = 2_000_000;
    for (let i = 0; i < 4; i++) rateLimit(key, opts, t0 + i);
    expect(rateLimit(key, opts, t0 + 60_001).allowed).toBe(true);
  });

  it("tracks keys independently", () => {
    const a = `a-${Math.random()}`;
    const b = `b-${Math.random()}`;
    const t0 = 3_000_000;
    for (let i = 0; i < 4; i++) rateLimit(a, opts, t0 + i);
    expect(rateLimit(a, opts, t0 + 10).allowed).toBe(false);
    expect(rateLimit(b, opts, t0 + 10).allowed).toBe(true);
  });

  it("prunes expired windows", () => {
    const key = `k3-${Math.random()}`;
    const t0 = 4_000_000;
    rateLimit(key, opts, t0);
    pruneRateLimitWindows(t0 + 120_000);
    // After pruning, a fresh window starts
    expect(rateLimit(key, opts, t0 + 120_001).remaining).toBe(2);
  });
});
