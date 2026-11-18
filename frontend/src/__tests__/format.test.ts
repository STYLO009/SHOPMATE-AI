import { describe, expect, it } from "vitest";
import { factorLabel, formatPrice, scorePercent } from "@/lib/format";

describe("format helpers", () => {
  it("formats INR prices with grouping", () => {
    const out = formatPrice(59990, "INR");
    expect(out).toContain("59,990");
  });

  it("falls back safely on unknown currencies", () => {
    const out = formatPrice(100, "XYZ");
    expect(out).toContain("100");
  });

  it("clamps scores into 0-100 percent", () => {
    expect(scorePercent(0.42)).toBe(42);
    expect(scorePercent(-1)).toBe(0);
    expect(scorePercent(2)).toBe(100);
  });

  it("humanises factor keys", () => {
    expect(factorLabel("budget_suitability")).toBe("Budget Suitability");
    expect(factorLabel("spec_match")).toBe("Spec Match");
  });
});
