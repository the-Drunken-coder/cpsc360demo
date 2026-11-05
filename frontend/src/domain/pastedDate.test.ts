import { describe, expect, it } from "vitest";
import { parsePastedDate } from "./pastedDate";

describe("pasted report dates", () => {
  it("accepts dates copied from report tables, including surrounding whitespace", () => {
    expect(parsePastedDate(" 2026-10-01\r\n")).toBe("2026-10-01");
  });

  it("accepts month/day/year dates and normalizes missing leading zeros", () => {
    expect(parsePastedDate("10/19/2026")).toBe("2026-10-19");
    expect(parsePastedDate("1/5/2026")).toBe("2026-01-05");
  });

  it("accepts a valid leap day", () => {
    expect(parsePastedDate("2/29/2024")).toBe("2024-02-29");
  });

  it.each(["2026-02-29", "2026-04-31", "13/01/2026", "2026-00-10", "2026-10-00", "0000-01-01"])("rejects the impossible date %s", (text) => {
    expect(parsePastedDate(text)).toBeUndefined();
  });

  it.each(["", "10/19/26", "2026-10-19 extra", "October 19", "2026/10/19"])("rejects incomplete or unsupported text %s", (text) => {
    expect(parsePastedDate(text)).toBeUndefined();
  });
});
