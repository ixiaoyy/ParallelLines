import type { CatalogProject } from "./model";

export interface CatalogAuthorRank {
  key: string;
  name: string;
  url?: string;
  projectCount: number;
  totalHearts: number;
  searchText: string;
}

interface AuthorGroup extends CatalogAuthorRank {
  names: Set<string>;
}

function normalizedName(name: string): string {
  return name.normalize("NFKC").trim().replace(/\s+/g, " ").toLowerCase();
}

function isReadmeLineCitation(url: URL): boolean {
  return /^#L\d+(?:-L\d+)?$/i.test(url.hash)
    && /\/README(?:\.[^/]+)?\.md$/i.test(url.pathname);
}

function profileUrl(value: string | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || isReadmeLineCitation(url)) {
      return null;
    }
    url.search = "";
    url.hash = "";
    url.pathname = url.pathname.replace(/\/+$/, "");
    // Linux.do 的个人主页与 /summary 指向同一作者，统一使用主页作为分组键。
    if (url.hostname === "linux.do" || url.hostname === "www.linux.do") {
      const profile = /^\/u\/([^/]+)(?:\/summary)?$/i.exec(url.pathname);
      if (profile) {
        url.hostname = "linux.do";
        url.pathname = `/u/${profile[1].toLowerCase()}`;
      }
    }
    return `${url.origin}${url.pathname}`;
  } catch {
    return null;
  }
}

// 公开目录由调用方提供；站内作品统一归为原创，来源 README 的逐条引用不视为作者主页。
export function catalogAuthorKey(project: CatalogProject): string | null {
  if (project.kind === "internal" || project.slug === "fablespace") return "original";
  const name = project.authorName?.trim();
  if (!name || normalizedName(name) === "待补充") return null;
  const url = profileUrl(project.authorUrl);
  return url ? `profile:${url}` : `name:${normalizedName(name)}`;
}

function displayName(name: string): string {
  return name.split(/\s+\/\s+/, 1)[0].trim();
}

export function rankCatalogAuthors(projects: CatalogProject[]): CatalogAuthorRank[] {
  const groups = new Map<string, AuthorGroup>();
  for (const project of projects) {
    const key = catalogAuthorKey(project);
    if (!key) continue;
    const authorName = key === "original" ? "原创" : project.authorName!.trim();
    const name = displayName(authorName);
    const url = key.startsWith("profile:") ? key.slice("profile:".length) : undefined;
    let group = groups.get(key);
    if (!group) {
      group = { key, name, url, projectCount: 0, totalHearts: 0, searchText: "", names: new Set() };
      groups.set(key, group);
    }
    // 同一主页可能有长短署名；展示简短名称，搜索仍覆盖所有原始署名。
    if (name.length < group.name.length || (name.length === group.name.length && name.localeCompare(group.name) < 0)) {
      group.name = name;
    }
    group.names.add(authorName);
    group.projectCount += 1;
    group.totalHearts += Math.max(0, project.ratingScoreSum ?? 0);
  }

  return [...groups.values()]
    .map(({ names, ...group }) => ({
      ...group,
      searchText: [...names, group.name].map(normalizedName).join(" "),
    }))
    .sort((left, right) => right.totalHearts - left.totalHearts
      || right.projectCount - left.projectCount
      || left.name.localeCompare(right.name, "zh-CN")
      || left.key.localeCompare(right.key));
}
