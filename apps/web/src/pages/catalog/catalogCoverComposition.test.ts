import { describe, expect, it } from "vitest";
import { arrangeMixedCovers } from "./catalogCoverComposition";

describe("mixed formal-cover composition", () => {
  const portrait = { key: "portrait", aspect: 439 / 721, heat: 2 };
  const quietWide = { key: "quiet", aspect: 960 / 452, heat: 1 };
  const popularWide = { key: "popular", aspect: 960 / 452, heat: 7 };
  const aspect = (item: typeof portrait) => item.aspect;
  const heat = (item: typeof portrait) => item.heat;

  it("puts a measured portrait in the portrait slot and preserves every real item", () => {
    const input = [portrait, quietWide, popularWide];
    expect(arrangeMixedCovers(input, aspect, heat)).toEqual([popularWide, quietWide, portrait]);
    expect(input).toEqual([portrait, quietWide, popularWide]);
  });

  it("does not guess orientation from a title, ID or missing measurement", () => {
    const input = [portrait, quietWide, popularWide];
    expect(arrangeMixedCovers(input, (item) => item === quietWide ? undefined : item.aspect, heat)).toEqual(input);
  });

  it("keeps incomplete groups and groups without a portrait intact", () => {
    const input = [quietWide, popularWide, { ...quietWide, key: "third" }, portrait];
    expect(arrangeMixedCovers(input, aspect, heat)).toEqual(input);
  });
});
