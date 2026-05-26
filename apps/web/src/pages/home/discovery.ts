export interface DiscoveryTab {
  key: "latest" | "hot" | "top" | "votes";
  label: string;
  description: string;
}

export const discoveryTabs: DiscoveryTab[] = [
  { key: "latest", label: "最新", description: "按最后回复时间排序" },
  { key: "hot", label: "热榜", description: "按社区热度排序" },
  { key: "top", label: "高信号", description: "优先看高赞和高回复主题" },
  { key: "votes", label: "投票", description: "按赞同数排序当前主题" },
];
