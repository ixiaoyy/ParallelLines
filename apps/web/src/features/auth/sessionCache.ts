import type { QueryClient } from "@tanstack/vue-query";

import { queryKeys } from "@/shared/api/queryKeys";
import type { UserPublic } from "./model";

/** 取消旧请求后清账号缓存；统一登录可检查当前身份，防止更早的切换覆盖新身份。 */
export async function resetQueryCacheForAuthChange(
  queryClient: QueryClient, currentUser: UserPublic | null, isCurrent = () => true,
): Promise<void> {
  await queryClient.cancelQueries();
  if (!isCurrent()) return;
  queryClient.removeQueries({ predicate: query => !(query.queryKey.length === 2 && query.queryKey[0] === "auth" && query.queryKey[1] === "me") });
  queryClient.setQueryData(queryKeys.currentUser, currentUser);
}
