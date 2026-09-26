import { describe, it, expect } from "vitest";
import { buildQuery } from "@/lib/api/client";

describe("buildQuery", () => {
  it("returns empty string for undefined", () => {
    expect(buildQuery(undefined)).toBe("");
  });

  it("returns empty string for an empty object", () => {
    expect(buildQuery({})).toBe("");
  });

  it("builds a single parameter", () => {
    expect(buildQuery({ q: "widget" })).toBe("?q=widget");
  });

  it("builds multiple parameters", () => {
    const result = buildQuery({ q: "widget", page: 2 });
    expect(result).toContain("q=widget");
    expect(result).toContain("page=2");
    expect(result.startsWith("?")).toBe(true);
  });

  it("drops null values", () => {
    expect(buildQuery({ q: "test", empty: null })).toBe("?q=test");
  });

  it("drops undefined values", () => {
    expect(buildQuery({ q: "test", empty: undefined })).toBe("?q=test");
  });

  it("drops empty string values", () => {
    expect(buildQuery({ q: "test", empty: "" })).toBe("?q=test");
  });

  it("repeats keys for array values", () => {
    const result = buildQuery({ status: ["ready", "waiting"] });
    expect(result).toBe("?status=ready&status=waiting");
  });

  it("handles boolean values", () => {
    expect(buildQuery({ active: true })).toBe("?active=true");
    expect(buildQuery({ active: false })).toBe("?active=false");
  });

  it("filters null items from arrays", () => {
    const result = buildQuery({ status: ["ready", null, "waiting"] });
    expect(result).toBe("?status=ready&status=waiting");
  });
});
