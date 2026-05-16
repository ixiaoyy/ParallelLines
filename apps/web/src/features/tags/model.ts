export interface TagResponse {
  id: string;
  name: string;
  slug: string;
  topic_count: number;
}

export interface TagItemVM {
  id: string;
  name: string;
  slug: string;
  topicCount: number;
}

export function toTagItem(tag: TagResponse): TagItemVM {
  return {
    id: tag.id,
    name: tag.name,
    slug: tag.slug,
    topicCount: tag.topic_count,
  };
}
