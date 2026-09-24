export const FISH_KINDS = [
  "whale",
  "koi",
  "sardine",
  "pufferfish",
  "goldfish",
  "clownfish",
  "angelfish",
  "betta",
] as const;

export type FishKind = (typeof FISH_KINDS)[number];
export type RandomSource = () => number;

export interface Point {
  readonly x: number;
  readonly y: number;
}
export interface PilePiece {
  readonly id: string;
  readonly kind: FishKind;
  readonly pile: Point;
  readonly spread: Point;
  readonly rotation: number;
  readonly scale: number;
  readonly layer: 0 | 1 | 2;
  readonly blockerIds?: readonly string[];
}

export interface TrayPiece {
  readonly id: string;
  readonly kind: FishKind;
}

export interface AmbientGameState {
  readonly pieces: readonly PilePiece[];
  readonly tray: readonly TrayPiece[];
  readonly clearCount: number;
  readonly level: number;
  readonly levelProgress: number;
  readonly nextPieceId: number;
}

export interface MissingSelection {
  readonly kind: "missing";
  readonly state: AmbientGameState;
}

export interface MovedSelection {
  readonly kind: "moved";
  readonly state: AmbientGameState;
  readonly selected: TrayPiece;
}

export interface CombinedSelection {
  readonly kind: "combined";
  readonly state: AmbientGameState;
  readonly selected: TrayPiece;
  readonly combined: readonly [TrayPiece, TrayPiece, TrayPiece];
  readonly fishKind: FishKind;
  readonly levelAdvanced: boolean;
  readonly fieldRefreshed: boolean;
}

export interface LostSelection {
  readonly kind: "lost";
  readonly state: AmbientGameState;
  readonly selected: TrayPiece;
  readonly tray: readonly TrayPiece[];
}

export type SelectionResult =
  | MissingSelection
  | MovedSelection
  | CombinedSelection
  | LostSelection;
