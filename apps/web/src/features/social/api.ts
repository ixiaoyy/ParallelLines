import { apiDelete, apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  PrivateMessageCreateRequest,
  PrivateMessageTopic,
  UserRelationshipKind,
  UserRelationshipState,
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

export function fetchPrivateMessages(): Promise<PrivateMessageTopic[]> {
  return apiGet<PrivateMessageTopic[]>("/users/messages");
}

export function createPrivateMessage(
  payload: PrivateMessageCreateRequest,
): Promise<PrivateMessageTopic> {
  return apiPost<PrivateMessageTopic, PrivateMessageCreateRequest>("/users/messages", payload);
}
