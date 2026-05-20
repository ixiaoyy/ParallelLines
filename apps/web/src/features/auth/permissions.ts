import type { UserPublic, UserRole } from "./model";

const GLOBAL_MODERATION_ROLES = new Set<UserRole>(["admin", "moderator"]);

export function isAdmin(user: Pick<UserPublic, "role"> | null | undefined): boolean {
  return user?.role === "admin";
}

export function canAccessModeration(user: Pick<UserPublic, "role"> | null | undefined): boolean {
  return Boolean(user && GLOBAL_MODERATION_ROLES.has(user.role));
}
