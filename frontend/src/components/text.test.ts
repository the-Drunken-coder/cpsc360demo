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

describe("evidence highlighting with accented words", () => {
  it("marks terms that end in a non-ASCII letter", () => {
    const text = "My GE Café range and the café oven";
    expect([...text.matchAll(termPattern(["ge café", "café"]))].map((m) => m[0])).toEqual(["GE Café", "café"]);
  });

  it("does not mark a term inside a longer accented word", () => {
    expect([..."cafés".matchAll(termPattern(["café"]))].map((m) => m[0])).toEqual([]);
  });
});
