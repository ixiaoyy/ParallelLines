import type { RandomSource } from "../engine";

export type CatReactionContext =
  | "idle"
  | "fed"
  | "full"
  | "sleeping"
  | "pet-head"
  | "pet-belly"
  | "pet-paws"
  | "play-pounce"
  | "play-bat"
  | "play-cuddle"
  | "unavailable";

export type CatBondStage = "newcomer" | "familiar" | "bonded";
export type CatPetZone = "head" | "belly" | "paws";
export type CatPlayVariant = "pounce" | "bat" | "cuddle";

export type CatMotion =
  | "idle"
  | "feeding"
  | "petting"
  | "playing"
  | "curious"
  | "resting"
  | "sleeping"
  | "loss";

export interface CatReaction {
  readonly id: string;
  readonly text: string;
}

const REACTIONS: Readonly<Record<CatReactionContext, readonly CatReaction[]>> = {
  idle: [
    { id: "idle-meow", text: "喵～" },
    { id: "idle-look", text: "看看这边" },
    { id: "idle-purr", text: "呼噜～" },
  ],
  fed: [
    { id: "fed-more", text: "再来一条？" },
    { id: "fed-tasty", text: "真好吃" },
  ],
  full: [
    { id: "full-belly", text: "好饱呀" },
    { id: "full-rest", text: "歇一会儿" },
  ],
  sleeping: [
    { id: "sleep-purr", text: "呼噜…" },
    { id: "sleep-dream", text: "梦见小鱼" },
  ],
  "pet-head": [
    { id: "pet-head-purr", text: "呼噜～" },
    { id: "pet-head-more", text: "再摸一下" },
  ],
  "pet-belly": [
    { id: "pet-belly-tickle", text: "痒痒的！" },
    { id: "pet-belly-giggle", text: "咯咯～" },
  ],
  "pet-paws": [
    { id: "pet-paws-touch", text: "碰个爪" },
    { id: "pet-paws-step", text: "踩踩～" },
  ],
  "play-pounce": [
    { id: "play-pounce-caught", text: "抓到啦" },
    { id: "play-pounce-again", text: "再滚一次" },
  ],
  "play-bat": [
    { id: "play-bat-high", text: "飞起来啦" },
    { id: "play-bat-tap", text: "啪嗒～" },
  ],
  "play-cuddle": [
    { id: "play-cuddle-mine", text: "抱住了" },
    { id: "play-cuddle-soft", text: "软乎乎的" },
  ],
  unavailable: [
    { id: "unavailable-triple", text: "要三条哦" },
    { id: "unavailable-wait", text: "先等等哦" },
  ],
};

/**
 * Maps a normalized vertical point on the cat target to one petting zone.
 * @param normalizedY Pointer Y position divided by the target height.
 * @returns Head, belly, or paws with out-of-range values safely clamped.
 */
export function resolveCatPetZone(normalizedY: number): CatPetZone {
  const y = Math.max(0, Math.min(1, normalizedY));
  if (y < 0.42) return "head";
  if (y < 0.76) return "belly";
  return "paws";
}

export function chooseCatReaction(
  context: CatReactionContext,
  previousId: string | null,
  random: RandomSource = Math.random,
): CatReaction {
  const pool = REACTIONS[context];
  const eligible = pool.length > 1
    ? pool.filter((reaction) => reaction.id !== previousId)
    : pool;
  const index = Math.min(
    eligible.length - 1,
    Math.floor(random() * eligible.length),
  );
  const reaction = eligible[index];
  if (!reaction) throw new Error(`Missing cat reaction for ${context}`);
  return reaction;
}
