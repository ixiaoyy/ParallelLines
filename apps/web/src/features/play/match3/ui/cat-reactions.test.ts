import { describe, expect, it } from "vitest";

import { chooseCatReaction, resolveCatPetZone } from "./cat-reactions";

describe("cat reactions", () => {
  it("does not repeat the previous eligible reaction", () => {
    const first = chooseCatReaction("idle", null, () => 0);
    const second = chooseCatReaction("idle", first.id, () => 0);

    expect(second.id).not.toBe(first.id);
  });

  it("keeps rest and yarn-play copy inside their own state", () => {
    expect(chooseCatReaction("full", null, () => 0).text).toBe("好饱呀");
    expect(chooseCatReaction("sleeping", null, () => 0).text).toBe("呼噜…");
    expect(chooseCatReaction("play-pounce", null, () => 0).text).toBe("抓到啦");
    expect(chooseCatReaction("play-bat", null, () => 0).text).toBe("飞起来啦");
    expect(chooseCatReaction("play-cuddle", null, () => 0).text).toBe("抱住了");
  });

  it("maps pointer height into clamped head, belly, and paws zones", () => {
    expect(resolveCatPetZone(-1)).toBe("head");
    expect(resolveCatPetZone(0.419)).toBe("head");
    expect(resolveCatPetZone(0.42)).toBe("belly");
    expect(resolveCatPetZone(0.759)).toBe("belly");
    expect(resolveCatPetZone(0.76)).toBe("paws");
    expect(resolveCatPetZone(2)).toBe("paws");
  });
});
