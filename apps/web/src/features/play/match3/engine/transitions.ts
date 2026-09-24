import { createLevelState, getLevelGoal } from "./pile";
import {
  type AmbientGameState,
  type FishKind,
  type RandomSource,
  type SelectionResult,
  type TrayPiece,
} from "./ambient-types";

export function restartAfterLoss(
  state: AmbientGameState,
  random: RandomSource = Math.random,
): AmbientGameState {
  return createLevelState(
    state.level,
    state.clearCount,
    state.nextPieceId,
    random,
    state.levelProgress,
  );
}

/**
 * Finds the earliest three small fish of one species that can combine.
 * @param tray Ordered tray contents after the current selection.
 * @param kind Species whose small fish should combine.
 * @returns An ordered triple, or null when fewer than three are present.
 */
function findCombination(
  tray: readonly TrayPiece[],
  kind: FishKind,
): readonly [TrayPiece, TrayPiece, TrayPiece] | null {
  const matches = tray.filter((piece) => piece.kind === kind).slice(0, 3);
  const [first, second, third] = matches;
  return first && second && third ? [first, second, third] : null;
}

export function selectPiece(
  state: AmbientGameState,
  pieceId: string,
  random: RandomSource = Math.random,
): SelectionResult {
  const piece = state.pieces.find((candidate) => candidate.id === pieceId);
  if (!piece) {
    return { kind: "missing", state };
  }

  const selected: TrayPiece = { id: piece.id, kind: piece.kind };
  const pieces = state.pieces.filter((candidate) => candidate.id !== pieceId);
  const tray = [...state.tray, selected];
  const combined = findCombination(tray, selected.kind);

  if (combined) {
    const combinedIds = new Set(combined.map((candidate) => candidate.id));
    const remainingTray = tray.filter((candidate) =>
      !combinedIds.has(candidate.id)
    );
    const clearCount = state.clearCount + 1;
    const levelProgress = state.levelProgress + 1;
    const levelAdvanced = levelProgress >= getLevelGoal(state.level);
    const fieldRefreshed = state.level > 1 || levelAdvanced;
    return {
      kind: "combined",
      selected,
      combined,
      fishKind: selected.kind,
      levelAdvanced,
      fieldRefreshed,
      state: fieldRefreshed
        ? createLevelState(
          levelAdvanced ? state.level + 1 : state.level,
          clearCount,
          state.nextPieceId,
          random,
          levelAdvanced ? 0 : levelProgress,
        )
        : {
          ...state,
          pieces,
          tray: remainingTray,
          clearCount,
          levelProgress,
        },
    };
  }

  if (tray.length === 7) {
    return {
      kind: "lost",
      state: restartAfterLoss(state, random),
      selected,
      tray,
    };
  }
  return { kind: "moved", state: { ...state, pieces, tray }, selected };
}
