interface FixtureProject { id: string; [key: string]: unknown }
interface FixtureCategory { id: string; slug: string; name: string; projects: FixtureProject[]; icon_url?: unknown }

/** 用冻结目录快照模拟新增公开分页接口；页面仍必须发真实分批请求，不能收到整类数据。 */
export function catalogPublicFixture(url: URL, categories: readonly FixtureCategory[]): object | undefined {
  const project = (entry: FixtureProject, category: FixtureCategory) => ({ ...entry, category_slug: category.slug, my_score: null });
  if (url.pathname === "/api/v1/catalog/overview") {
    const allowed = url.searchParams.has("hero_slugs") ? new Set((url.searchParams.get("hero_slugs") ?? "").split(",").filter(Boolean)) : undefined;
    const all = categories.flatMap((category) => category.projects.map((entry) => project(entry, category)))
      .filter((entry) => !allowed || allowed.has(String(entry.slug)));
    const score = (entry: FixtureProject) => {
      const value = (entry.ai_rating as { score?: unknown } | null)?.score;
      return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 10 ? value : -1;
    };
    all.sort((left, right) => score(right) - score(left));
    const offset = Number(url.searchParams.get("hero_offset") ?? 0);
    return { data: {
      categories: categories.map((category) => ({ id: category.id, slug: category.slug, name: category.name, icon_url: category.icon_url ?? null, total: category.projects.length })),
      hero: { projects: all.slice(offset, offset + 6), total: all.length, next_offset: offset + 6 < all.length ? offset + 6 : null },
    } };
  }
  const match = /^\/api\/v1\/catalog\/categories\/([^/]+)\/projects$/.exec(url.pathname);
  if (!match) return undefined;
  const category = categories.find((entry) => entry.slug === decodeURIComponent(match[1]!));
  if (!category) return { error: { code: "category_not_found", message: "Fixture category not found" } };
  const priority = new Map((url.searchParams.get("priority_slugs") ?? "").split(",").map((slug, index) => [slug, index]));
  const ordered = [...category.projects].sort((left, right) => {
    const created = Date.parse(String(right.created_at)) - Date.parse(String(left.created_at));
    if (created) return created;
    const seeded = (priority.get(String(left.slug)) ?? Number.MAX_SAFE_INTEGER) - (priority.get(String(right.slug)) ?? Number.MAX_SAFE_INTEGER);
    return seeded || right.id.length - left.id.length || (left.id < right.id ? 1 : left.id > right.id ? -1 : 0);
  });
  const offset = Number((url.searchParams.get("cursor") ?? "fixture:0").replace(/^fixture:/, ""));
  const limit = Number(url.searchParams.get("limit"));
  const end = offset + limit;
  return { data: { category_id: category.id, category_slug: category.slug, projects: ordered.slice(offset, end).map((entry) => project(entry, category)),
    total: ordered.length, has_more: end < ordered.length, next_cursor: end < ordered.length ? `fixture:${end}` : null } };
}
