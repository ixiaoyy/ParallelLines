import { apiDelete, apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  PrivateMessageCreateRequest,
  PrivateMessageTopic,
  UserRelationshipKind,
  UserRelationshipListKind,
  UserRelationshipState,
  UserRelationshipUser,
} from "./model";

export function fetchUserRelationship(username: string): Promise<UserRelationshipState> {
  return apiGet<UserRelationshipState>(`/users/${encodeURIComponent(username)}/relationship`);
}

export function setUserRelationship(
  username: string,
  kind: UserRelationshipKind,
  active: boolean,
): Promise<UserRelationshipState> {
  const path = `/users/${encodeURIComponent(username)}/${kind}`;
  return active ? apiPut<UserRelationshipState, object>(path, {}) : apiDelete<UserRelationshipState>(path);
}

// fetchUserRelationshipUsers 用途：读取某个成员的关注/粉丝列表。
// 关键参数：kind 控制 following/followers 方向。
// 返回值/副作用：返回 API 用户卡片数组，不修改本地或服务端状态。
export function fetchUserRelationshipUsers(
  username: string,
  kind: UserRelationshipListKind,
): Promise<UserRelationshipUser[]> {
  return apiGet<UserRelationshipUser[]>(
    `/users/${encodeURIComponent(username)}/relationships/${kind}`,
  );
}

export function fetchPrivateMessages(): Promise<PrivateMessageTopic[]> {
  return apiGet<PrivateMessageTopic[]>("/users/messages");
}

export function createPrivateMessage(
  payload: PrivateMessageCreateRequest,
): Promise<PrivateMessageTopic> {
  return apiPost<PrivateMessageTopic, PrivateMessageCreateRequest>("/users/messages", payload);
}
