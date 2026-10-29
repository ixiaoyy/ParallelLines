import type { CatalogJsonValue, CatalogProject } from "./model";

/** Stable ties retain the caller's order without converting exact string IDs to numbers. */
export function compareAiRating(left: CatalogProject, right: CatalogProject): number {
  const leftScore = aiScore(left);
  const rightScore = aiScore(right);
  if (leftScore === null) return rightScore === null ? 0 : 1;
  if (rightScore === null) return -1;
  return rightScore - leftScore;
}

function aiScore(project: CatalogProject): number | null {
  const score = project.aiRating?.score;
  return typeof score === "number" && Number.isFinite(score) && score >= 0 && score <= 10 ? score : null;
}

function isObject(value: CatalogJsonValue | undefined): value is { [key: string]: CatalogJsonValue } {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Only explicit completed device checks prove compatibility; platform/browser text does not. */
function deviceEvidence(project: CatalogProject, isMobile: boolean | undefined): boolean | null {
  if (isMobile === undefined) return null;
  const checks = project.aiRating?.playScope.device_checks;
  if (!isObject(checks)) return null;
  const check = checks[isMobile ? "mobile" : "desktop"];
  return isObject(check) && check.tested === true && typeof check.compatible === "boolean"
    ? check.compatible : null;
}

/**
 * Score is the primary order. Ties rotate categories and may use actual device
 * checks; unknown devices stay eligible. Explicit incompatibility only filters
 * recommendations for that device. At most one unscored game fills spare space
 * for exploration. With no AI scores, retain the original recommendation list.
 */
export function selectAiRecommendations<T extends CatalogProject & { categorySlug: string }>(
  projects: T[], limit = 6, context?: { isMobile?: boolean },
): T[] {
  const size = Number.isFinite(limit) ? Math.max(0, Math.floor(limit)) : 0;
  if (!size) return [];
  if (!projects.some((project) => aiScore(project) !== null)) return projects.slice(0, size);

  const eligible = projects.filter((project) => deviceEvidence(project, context?.isMobile) !== false);
  const remaining = eligible.filter((project) => aiScore(project) !== null).sort(compareAiRating);
  const chosen: T[] = [];
  const categories = new Map<string, number>();
  while (remaining.length && chosen.length < size) {
    const topScore = aiScore(remaining[0]);
    let index = 0;
    for (let candidate = 1; candidate < remaining.length && aiScore(remaining[candidate]) === topScore; candidate += 1) {
      const current = remaining[index];
      const next = remaining[candidate];
      const currentCount = categories.get(current.categorySlug) ?? 0;
      const nextCount = categories.get(next.categorySlug) ?? 0;
      if (nextCount < currentCount || (nextCount === currentCount
        && deviceEvidence(next, context?.isMobile) === true
        && deviceEvidence(current, context?.isMobile) !== true)) index = candidate;
    }
    const [project] = remaining.splice(index, 1);
    chosen.push(project);
    categories.set(project.categorySlug, (categories.get(project.categorySlug) ?? 0) + 1);
  }
  if (chosen.length < size) {
    const exploration = eligible.filter((project) => aiScore(project) === null)
      .sort((left, right) => {
        const leftTime = Date.parse(left.createdAt);
        const rightTime = Date.parse(right.createdAt);
        return (Number.isFinite(rightTime) ? rightTime : 0) - (Number.isFinite(leftTime) ? leftTime : 0);
      })[0];
    if (exploration) chosen.push(exploration);
  }
  return chosen;
}
