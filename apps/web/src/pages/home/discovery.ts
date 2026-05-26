export interface DiscoveryTab {
  key: "latest" | "hot" | "top";
  label: string;
}

export const discoveryTabs: DiscoveryTab[] = [
  { key: "latest", label: "最新" },
  { key: "hot", label: "热门" },
  { key: "top", label: "精华" },
];
