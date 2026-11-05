import { describe, expect, it } from "vitest";
import { termPattern } from "./text";

describe("evidence highlighting", () => {
  it("marks the evidence phrase and not longer words that start with it", () => {
    const text = "a pretty big fire outside of the sealed direct vent fireplace";
    expect([...text.matchAll(termPattern(["fire"]))].map((m) => m[0])).toEqual(["fire"]);
  });

  it("matches multi-word phrases case-insensitively", () => {
    expect([..."The unit CAUGHT FIRE twice".matchAll(termPattern(["caught fire"]))].map((m) => m[0])).toEqual(["CAUGHT FIRE"]);
  });
});
