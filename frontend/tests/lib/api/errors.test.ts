import { describe, it, expect } from "vitest";
import { ApiError } from "@/lib/api/errors";

describe("ApiError", () => {
  const makeError = (status: number, overrides = {}) =>
    new ApiError(status, {
      code: "TEST_ERROR",
      message: "something broke",
      details: [],
      request_id: "req-123",
      ...overrides,
    });

  it("exposes status and code", () => {
    const err = makeError(400);
    expect(err.status).toBe(400);
    expect(err.code).toBe("TEST_ERROR");
    expect(err.message).toBe("something broke");
    expect(err.requestId).toBe("req-123");
  });

  it("isUnauthenticated is true for 401", () => {
    expect(makeError(401).isUnauthenticated).toBe(true);
    expect(makeError(403).isUnauthenticated).toBe(false);
  });

  it("isForbidden is true for 403", () => {
    expect(makeError(403).isForbidden).toBe(true);
    expect(makeError(401).isForbidden).toBe(false);
  });

  it("isNotFound is true for 404", () => {
    expect(makeError(404).isNotFound).toBe(true);
    expect(makeError(400).isNotFound).toBe(false);
  });

  it("isUserFixable is true for 4xx except 401", () => {
    expect(makeError(400).isUserFixable).toBe(true);
    expect(makeError(422).isUserFixable).toBe(true);
    expect(makeError(401).isUserFixable).toBe(false);
    expect(makeError(500).isUserFixable).toBe(false);
  });

  it("fieldErrors maps details by field name", () => {
    const err = makeError(422, {
      details: [
        { field: "email", message: "required" },
        { field: "name", message: "too short" },
        { field: "email", message: "duplicate" }, // first wins
      ],
    });
    expect(err.fieldErrors).toEqual({
      email: "required",
      name: "too short",
    });
  });

  it("fieldErrors returns empty object when no details", () => {
    expect(makeError(400).fieldErrors).toEqual({});
  });

  it("handles null request_id", () => {
    const err = makeError(400, { request_id: null });
    expect(err.requestId).toBeNull();
  });
});
