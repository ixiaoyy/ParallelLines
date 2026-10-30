import { computed, watch } from "vue";
import type { Ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { LocationQuery, LocationQueryRaw } from "vue-router";
import { isCatalogTopicId, type CatalogTopicId } from "./catalogTopics";

export type CatalogNavId = "home" | "latest" | "hot" | "site" | "wanted" | "recent" | "authors" | "contributors";
export type CatalogFeed = "discovery" | "latest" | "hot";

interface CatalogNavigationState {
  view: "games" | "authors" | "contributors";
  scope: "all" | "wanted" | "recent";
  category: string;
  author: string | null;
  sort: "latest" | "hot";
  feed: CatalogFeed;
  search: string;
}

interface CatalogNavigationRefs {
  catalogView: Ref<CatalogNavigationState["view"]>;
  libraryScope: Ref<CatalogNavigationState["scope"]>;
  selectedCategory: Ref<string>;
  selectedAuthorKey: Ref<string | null>;
  sortMode: Ref<CatalogNavigationState["sort"]>;
  feed: Ref<CatalogFeed>;
  search: Ref<string>;
  searchInput: Ref<string>;
}

const defaults: CatalogNavigationState = {
  view: "games", scope: "all", category: "all", author: null,
  sort: "latest", feed: "discovery", search: "",
};

/** Parse only known directory query fields; preserve unrelated route parameters on writes. */
export function parseCatalogNavigation(query: LocationQuery): CatalogNavigationState {
  const text = (key: string): string => typeof query[key] === "string" ? query[key] : "";
  const feed = text("feed");
  return {
    view: text("view") === "authors" ? "authors" : text("view") === "contributors" ? "contributors" : "games",
    scope: text("scope") === "wanted" ? "wanted" : text("scope") === "recent" ? "recent" : "all",
    category: text("category") || "all",
    author: text("author") || null,
    sort: text("sort") === "hot" || feed === "hot" ? "hot" : "latest",
    feed: feed === "latest" || feed === "hot" ? feed : "discovery",
    search: text("q"),
  };
}

/** The recommendation topic is URL-backed, but is never a global catalog filter. */
export function parseCatalogHeroTopic(query: LocationQuery): CatalogTopicId {
  const topic = query.topic;
  return typeof topic === "string" && isCatalogTopicId(topic) ? topic : "all";
}

function stateQuery(state: CatalogNavigationState, existing: LocationQuery): LocationQueryRaw {
  const query: LocationQueryRaw = { ...existing };
  for (const key of ["view", "scope", "category", "author", "sort", "feed", "layout", "q"]) delete query[key];
  if (state.view !== "games") query.view = state.view;
  if (state.scope !== "all") query.scope = state.scope;
  if (state.category !== "all") query.category = state.category;
  if (state.author) query.author = state.author;
  if (state.sort !== "latest") query.sort = state.sort;
  if (state.feed !== "discovery") query.feed = state.feed;
  if (state.search) query.q = state.search;
  return query;
}

/** Keep catalog state in the URL so rail navigation, reload, and browser Back agree. */
export function useCatalogNavigation(refs: CatalogNavigationRefs) {
  const route = useRoute();
  const router = useRouter();
  const readState = (): CatalogNavigationState => ({
    view: refs.catalogView.value, scope: refs.libraryScope.value,
    category: refs.selectedCategory.value, author: refs.selectedAuthorKey.value,
    sort: refs.sortMode.value, feed: refs.feed.value,
    search: refs.search.value,
  });
  const applyState = (state: CatalogNavigationState): void => {
    refs.catalogView.value = state.view;
    refs.libraryScope.value = state.scope;
    refs.selectedCategory.value = state.category;
    refs.selectedAuthorKey.value = state.author;
    refs.sortMode.value = state.sort;
    refs.feed.value = state.feed;
    refs.search.value = state.search;
    refs.searchInput.value = state.search;
  };
  watch(() => route.query, (query) => applyState(parseCatalogNavigation(query)), { immediate: true, flush: "sync" });
  watch(readState, (state) => {
    if (state.feed !== "discovery" && state.feed !== state.sort) {
      refs.feed.value = state.sort;
      return;
    }
    if (JSON.stringify(state) === JSON.stringify(parseCatalogNavigation(route.query))) return;
    void router.replace({ path: route.path, query: stateQuery(state, route.query), hash: route.hash });
  });

  const openState = (state: CatalogNavigationState): void => {
    void router.push({ path: route.path, query: stateQuery(state, route.query) });
  };
  const active = computed<CatalogNavId | "category" | "search" | "author">(() => {
    const state = readState();
    if (state.view !== "games") return state.view;
    if (state.scope !== "all") return state.scope;
    if (state.author) return state.author === "original" ? "site" : "author";
    if (state.category !== "all") return "category";
    if (state.search.trim()) return "search";
    return state.feed === "discovery" ? "home" : state.feed;
  });

  return {
    active,
    heroTopic: computed(() => parseCatalogHeroTopic(route.query)),
    navigate(id: CatalogNavId): void {
      const state = { ...defaults };
      if (id === "authors" || id === "contributors") state.view = id;
      else if (id === "site") state.author = "original";
      else if (id === "wanted" || id === "recent") state.scope = id;
      else if (id === "latest" || id === "hot") { state.feed = id; state.sort = id; }
      openState(state);
    },
    category(slug: string): void { openState({ ...defaults, category: slug }); },
    author(key: string): void { openState({ ...defaults, author: key }); },
    topic(id: CatalogTopicId): void {
      const query: LocationQueryRaw = { ...route.query };
      delete query.topic;
      if (id !== "all") query.topic = id;
      void router.push({ path: route.path, query, hash: route.hash });
    },
  };
}
