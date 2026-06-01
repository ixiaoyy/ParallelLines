import type { BoardSummary } from "./model";

const FEEDBACK_BOARD_SLUG = "feedback";

/**
 * Sorts board lists while keeping 社区反馈 as the final visible board.
 * `boards` is the source list and `compare` optionally applies a normal ordering before the final-position rule.
 * Return value is a new array; side effect: none.
 */
export function sortBoardsWithFeedbackLast(
  boards: BoardSummary[],
  compare?: (left: BoardSummary, right: BoardSummary) => number,
): BoardSummary[] {
  return [...boards].sort((left, right) => {
    const leftIsFeedback = left.slug === FEEDBACK_BOARD_SLUG;
    const rightIsFeedback = right.slug === FEEDBACK_BOARD_SLUG;

    if (leftIsFeedback !== rightIsFeedback) {
      return leftIsFeedback ? 1 : -1;
    }

    return compare?.(left, right) ?? 0;
  });
}
