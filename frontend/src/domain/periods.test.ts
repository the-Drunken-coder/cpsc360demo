import { describe, expect, it } from "vitest";
import { clampRange, firstIncompletePeriod, periodLabel, periodRange } from "./periods";

describe("trend periods", () => {
  it("maps a chart bucket to the inclusive report-date range it counts", () => {
    expect(periodRange("2012-01-01", "quarter")).toEqual({ from: "2012-01-01", to: "2012-03-31" });
    expect(periodRange("2024-02-01", "month")).toEqual({ from: "2024-02-01", to: "2024-02-29" });
    expect(periodRange("2026-01-01", "year")).toEqual({ from: "2026-01-01", to: "2026-12-31" });
  });

  it("keeps a drill-down inside the date filters already applied", () => {
    expect(clampRange({ from: "2026-01-01", to: "2026-03-31" }, { from: "2026-02-15" })).toEqual({ from: "2026-02-15", to: "2026-03-31" });
  });

  it("labels buckets the way analysts read them", () => {
    expect(periodLabel("2012-04-01", "quarter")).toBe("2012 Q2");
    expect(periodLabel("2012-04-01", "month")).toBe("2012-04");
  });
});

describe("incomplete trend buckets", () => {
  it("shades the bucket that contains the cutoff, not just the days after it", () => {
    const months = ["2026-08-01", "2026-09-01", "2026-10-01"];
    expect(firstIncompletePeriod(months, "month", "2026-09-19")).toBe("2026-09-01");
    expect(firstIncompletePeriod(["2026-01-01", "2026-04-01", "2026-07-01"], "quarter", "2026-09-19")).toBe("2026-07-01");
    expect(firstIncompletePeriod(months, "month", "2026-11-05")).toBeUndefined();
  });
});
