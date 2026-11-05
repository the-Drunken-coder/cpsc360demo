import { describe, expect, it } from "vitest";
import { compactFilters, explorerHref, parseFilters, toSearchParams, toggleListValue } from "./filters";

describe("filter codec", () => {
  it("round-trips every filter kind through the URL", () => {
    const filters = {
      q: '"pressure cooker" lid',
      hazard: ["burn" as const, "fire" as const],
      product_code: ["1512"],
      injury_only: true,
      has_company_comment: false,
      in_investigation: 7,
      report_date_from: "2026-06-22",
    };
    expect(parseFilters(toSearchParams(filters))).toEqual(filters);
  });

  it("drops unknown hazards, empty values, and malformed numbers from a pasted URL", () => {
    const params = new URLSearchParams("hazard=fire&hazard=lava&state=&in_investigation=abc&injury_only=maybe&q=");
    expect(parseFilters(params)).toEqual({ hazard: ["fire"] });
  });

  it("turns API filter payloads with nulls and empty lists into only the set constraints", () => {
    const payload = { q: null, product_category: [], product_code: ["1512"], report_date_from: "2026-06-22", injury_only: null };
    expect(explorerHref(compactFilters(payload))).toBe("/?product_code=1512&report_date_from=2026-06-22");
  });

  it("toggling the last value of a list removes the filter", () => {
    const once = toggleListValue({}, "hazard", "fire");
    expect(once).toEqual({ hazard: ["fire"] });
    expect(toggleListValue(once, "hazard", "fire")).toEqual({});
  });
});
