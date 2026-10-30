/** Arrange complete, measured triples only; no game IDs or category membership. */
export function arrangeMixedCovers<T>(
  projects: readonly T[],
  aspectFor: (project: T) => number | undefined,
  priorityFor: (project: T) => number,
): T[] {
  const arranged = [...projects];
  for (let offset = 0; offset + 2 < projects.length; offset += 3) {
    const triple = projects.slice(offset, offset + 3).map((project) => ({ project, aspect: aspectFor(project) }));
    if (triple.some(({ aspect }) => aspect === undefined || !Number.isFinite(aspect) || aspect <= 0)) continue;
    const portrait = triple.filter(({ aspect }) => aspect! < .9);
    const landscape = triple.filter(({ aspect }) => aspect! >= 1.2);
    if (portrait.length !== 1 || landscape.length !== 2) continue;
    // Width wins; equal-size artwork uses the existing genuine heat as a tie-break.
    landscape.sort((left, right) => right.aspect! - left.aspect! || priorityFor(right.project) - priorityFor(left.project));
    arranged.splice(offset, 3, landscape[0]!.project, landscape[1]!.project, portrait[0]!.project);
  }
  return arranged;
}
