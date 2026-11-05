import { describe, expect, it } from "vitest";
import { isDrillable, withGroup } from "./drilldown";

describe("analytics drill-down", () => {
  it("keeps an active hazard filter and requires the clicked hazard too", () => {
    expect(withGroup({ hazard: ["fire"], report_date_from: "2026-01-01" }, "hazard", "burn"))
      .toEqual({ hazard: ["fire"], hazard_all: ["burn"], report_date_from: "2026-01-01" });
  });

  it("filters on the clicked hazard alone when no hazard filter is active", () => {
    expect(withGroup({ product_code: ["1512"] }, "hazard", "skin_irritation"))
      .toEqual({ product_code: ["1512"], hazard: ["skin_irritation"] });
  });

  it("narrows single-valued fields to the clicked group", () => {
    expect(withGroup({ product_code: ["1512", "278"] }, "product_code", "1512")).toEqual({ product_code: ["1512"] });
  });

  it("does not drill into folded or missing-value buckets", () => {
    expect(isDrillable("__other__")).toBe(false);
    expect(isDrillable("__unknown__")).toBe(false);
    expect(isDrillable("Texas")).toBe(true);
  });
});
